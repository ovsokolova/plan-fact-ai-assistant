from __future__ import annotations

from pathlib import Path

import pytest

from src.rag import (
    ChromaVectorStore,
    chunk_text,
    ingest_directory,
    make_store,
    read_document,
    retrieve,
)


@pytest.fixture
def store(tmp_path: Path) -> ChromaVectorStore:
    s = ChromaVectorStore(persist_dir=tmp_path / "chroma")
    return s


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    d = tmp_path / "docs"
    d.mkdir()
    (d / "contract_45_2024.txt").write_text(
        "Договор № 45/2024. Пункт 4.2. Оплата производится авансом "
        "в размере 100% в течение 5 рабочих дней с даты подписания акта. "
        "Маркетинговые услуги оказываются ежемесячно.",
        encoding="utf-8",
    )
    (d / "regulation_budget.txt").write_text(
        "Регламент бюджетирования. Перенос расходов между периодами "
        "согласовывается с финансовым блоком.",
        encoding="utf-8",
    )
    return d


def test_chunk_text_basic() -> None:
    text = "a" * 2000
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) >= 3
    assert all(len(c) <= 800 for c in chunks)


def test_chunk_text_invalid_params() -> None:
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=100, overlap=200)


def test_read_document_txt(tmp_path: Path) -> None:
    p = tmp_path / "doc.txt"
    p.write_text("hello world", encoding="utf-8")
    pages = read_document(p)
    assert pages == [(1, "hello world")]


def test_read_document_missing() -> None:
    with pytest.raises(FileNotFoundError):
        read_document("does-not-exist.txt")


def test_empty_index_returns_empty(store: ChromaVectorStore) -> None:
    assert store.count() == 0
    assert retrieve(store, "anything") == []


def test_ingest_directory(store: ChromaVectorStore, docs_dir: Path) -> None:
    n = ingest_directory(store, docs_dir)
    assert n > 0
    assert store.count() == n


def test_retrieve_finds_relevant(store: ChromaVectorStore, docs_dir: Path) -> None:
    ingest_directory(store, docs_dir)
    chunks = retrieve(store, "предоплата маркетинг договор", k=5, min_score=0.0)
    assert len(chunks) > 0
    # хотя бы один из чанков — из договора
    sources = {c.source for c in chunks}
    assert "contract_45_2024.txt" in sources


def test_retrieve_top_k_limit(store: ChromaVectorStore, docs_dir: Path) -> None:
    ingest_directory(store, docs_dir)
    chunks = retrieve(store, "оплата", k=1, min_score=0.0)
    assert len(chunks) <= 1


def test_retrieve_min_score_filter(store: ChromaVectorStore, docs_dir: Path) -> None:
    ingest_directory(store, docs_dir)
    # очень высокий порог → ничего не пройдёт
    chunks = retrieve(store, "xyz unrelated query", k=5, min_score=0.999)
    assert chunks == []


def test_ingest_empty_dir(store: ChromaVectorStore, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert ingest_directory(store, empty) == 0
    assert store.count() == 0


def test_make_store_chroma(tmp_path: Path) -> None:
    s = make_store(backend="chroma", persist_dir=tmp_path / "c2")
    assert isinstance(s, ChromaVectorStore)


def test_make_store_unknown_backend(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="не реализован"):
        make_store(backend="pinecone", persist_dir=tmp_path / "c3")