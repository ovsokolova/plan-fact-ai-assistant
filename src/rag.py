"""RAG: индексация документов и поиск релевантных фрагментов.

Соответствует openspec/specs/rag-retrieval.md.
По умолчанию используется Chroma (persistent client).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

import chromadb
from chromadb.api.models.Collection import Collection


DEFAULT_CHROMA_DIR = ".chroma"
DEFAULT_COLLECTION = "documents"


@dataclass
class Chunk:
    """Фрагмент документа с метаданными."""

    text: str
    source: str
    page: int | None
    clause: str | None
    score: float


class VectorStore(Protocol):
    """Абстракция векторного хранилища (см. ADR-0002)."""

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None: ...
    def query(self, query_texts: list[str], n_results: int) -> dict[str, Any]: ...
    def count(self) -> int: ...
    def reset(self) -> None: ...


class ChromaVectorStore:
    """Chroma-реализация VectorStore (default для MVP)."""

    def __init__(
        self,
        persist_dir: str | Path = DEFAULT_CHROMA_DIR,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection: Collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def query(self, query_texts: list[str], n_results: int) -> dict[str, Any]:
        if self._collection.count() == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        n = min(n_results, self._collection.count())
        return self._collection.query(query_texts=query_texts, n_results=n)

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        self._client.delete_collection(self._collection.name)
        self._collection = self._client.get_or_create_collection(
            name=DEFAULT_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )


# ---------------------------------------------------------------------------
# Чанкинг
# ---------------------------------------------------------------------------


def _read_pdf(path: Path) -> list[tuple[int, str]]:
    """Возвращает список (номер_страницы, текст)."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    out: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            out.append((i, text))
    return out


def _read_docx(path: Path) -> list[tuple[int, str]]:
    from docx import Document

    doc = Document(str(path))
    # DOCX не имеет страниц — используем 1 как условную
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(1, text)] if text.strip() else []


def _read_text(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [(1, text)] if text.strip() else []


def read_document(path: str | Path) -> list[tuple[int, str]]:
    """Читает PDF/DOCX/TXT → список (страница, текст)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Документ не найден: {p}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(p)
    if suffix in (".docx", ".doc"):
        return _read_docx(p)
    if suffix in (".txt", ".md"):
        return _read_text(p)
    raise ValueError(f"Неподдерживаемый формат: {suffix}")


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """Простой чанкинг по символам с overlap.

    Для MVP без токенизатора — приблизительно 1 токен ≈ 4 символа,
    значит 800 символов ≈ 200 токенов.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size должен быть больше overlap")
    chunks: list[str] = []
    step = chunk_size - overlap
    for start in range(0, max(len(text), 1), step):
        piece = text[start : start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        if start + chunk_size >= len(text):
            break
    return chunks


def _make_id(source: str, page: int, idx: int, text: str) -> str:
    h = hashlib.sha1(f"{source}:{page}:{idx}:{text[:64]}".encode("utf-8")).hexdigest()[:16]
    return f"{Path(source).stem}-{page}-{idx}-{h}"


def ingest_directory(
    store: VectorStore,
    directory: str | Path,
    *,
    chunk_size: int = 800,
    overlap: int = 100,
) -> int:
    """Индексирует все PDF/DOCX/TXT/MD из директории. Возвращает число чанков."""
    d = Path(directory)
    if not d.exists():
        return 0

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for path in sorted(d.rglob("*")):
        if path.suffix.lower() not in (".pdf", ".docx", ".doc", ".txt", ".md"):
            continue
        try:
            pages = read_document(path)
        except Exception as e:  # noqa: BLE001
            print(f"[rag] skip {path}: {e}")
            continue
        for page, text in pages:
            for idx, piece in enumerate(chunk_text(text, chunk_size=chunk_size, overlap=overlap)):
                ids.append(_make_id(str(path), page, idx, piece))
                documents.append(piece)
                metadatas.append(
                    {
                        "source": path.name,
                        "path": str(path),
                        "page": page,
                        "clause": None,
                    }
                )

    store.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def retrieve(
    store: VectorStore,
    query: str,
    *,
    k: int = 5,
    min_score: float = 0.75,
) -> list[Chunk]:
    """Возвращает top-k релевантных чанков.

    Chroma возвращает cosine *distance* (0 = идентично, 2 = противоположно).
    Конвертируем в score = 1 - distance.
    """
    if not query.strip() or store.count() == 0:
        return []

    res = store.query(query_texts=[query], n_results=k)
    ids = res.get("ids", [[]])[0]
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    out: list[Chunk] = []
    for _id, doc, meta, dist in zip(ids, docs, metas, dists, strict=False):
        score = max(0.0, 1.0 - float(dist))
        if score < min_score:
            continue
        out.append(
            Chunk(
                text=doc,
                source=str(meta.get("source", "unknown")),
                page=meta.get("page"),
                clause=meta.get("clause"),
                score=score,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_store(
    backend: str | None = None,
    persist_dir: str | Path | None = None,
) -> VectorStore:
    """Фабрика вектор-стора. По умолчанию — Chroma."""
    backend = (backend or os.getenv("VECTOR_STORE") or "chroma").lower()
    persist_dir = persist_dir or os.getenv("CHROMA_DIR", DEFAULT_CHROMA_DIR)
    if backend == "chroma":
        return ChromaVectorStore(persist_dir=persist_dir)
    raise ValueError(f"Backend '{backend}' не реализован в MVP (см. ADR-0002).")