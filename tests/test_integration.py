"""Интеграционные тесты: RAG + LLM (с моком LLMClient)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.llm_agent import LLMClient, LLMConfig, ReportJSON, generate
from src.rag import ChromaVectorStore, ingest_directory, retrieve


@pytest.fixture
def variance_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account": ["Маркетинг"],
            "period": ["2025-01"],
            "plan": [1_000_000.0],
            "fact": [1_350_000.0],
            "abs_variance": [350_000.0],
            "rel_variance": [0.35],
            "status": ["red"],
            "owner": ["CMO"],
        }
    )


@pytest.fixture
def rag_store(tmp_path: Path) -> ChromaVectorStore:
    store = ChromaVectorStore(persist_dir=tmp_path / "chroma")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "contract.txt").write_text(
        "Договор № 45/2024. Пункт 4.2. Оплата производится авансом 100%.",
        encoding="utf-8",
    )
    ingest_directory(store, docs)
    return store


def _make_mock_client(*, available: bool, response: str = "", model: str = "mock-model") -> MagicMock:
    """Создаёт MagicMock с настроенными config и available."""
    mock = MagicMock(spec=LLMClient)
    mock.available.return_value = available
    mock.config = LLMConfig(provider="openai", model=model, api_key="test")
    if response:
        mock.complete.return_value = response
    return mock


def test_full_pipeline_retrieve_then_generate(variance_df, rag_store) -> None:
    """RAG -> chunks -> LLM (mock) -> ReportJSON."""
    chunks = retrieve(rag_store, "предоплата маркетинг", k=3, min_score=0.0)
    assert len(chunks) >= 1

    fake_json = {
        "summary": "Перерасход маркетинга связан с предоплатой.",
        "items": [
            {
                "account": "Маркетинг",
                "period": "2025-01",
                "abs_variance": 350000.0,
                "rel_variance": 0.35,
                "hypotheses": ["Предоплата по п. 4.2"],
                "references": [
                    {
                        "source": "contract.txt",
                        "page": 1,
                        "clause": "4.2",
                        "quote": "Оплата производится авансом 100%",
                    }
                ],
                "questions": ["Согласована ли предоплата?"],
            }
        ],
    }

    mock_client = _make_mock_client(
        available=True,
        response=json.dumps(fake_json, ensure_ascii=False),
        model="mock-model",
    )

    report = generate(variance_df, chunks, client=mock_client)

    assert isinstance(report, ReportJSON)
    assert report.meta.model == "mock-model"
    assert len(report.items) == 1
    assert report.items[0].references[0].clause == "4.2"


def test_pipeline_fallback_when_llm_unavailable(variance_df, rag_store) -> None:
    """Если LLM недоступна — отчёт всё равно генерируется (fallback)."""
    chunks = retrieve(rag_store, "предоплата", k=3, min_score=0.0)

    mock_client = _make_mock_client(available=False)

    report = generate(variance_df, chunks, client=mock_client)
    assert report.meta.model == "fallback"
    assert len(report.items) == 1


def test_rag_empty_then_generate(variance_df, tmp_path: Path) -> None:
    """Пустой RAG-индекс не ломает генерацию."""
    empty_store = ChromaVectorStore(persist_dir=tmp_path / "empty")
    chunks = retrieve(empty_store, "ничего", k=5, min_score=0.0)
    assert chunks == []

    mock_client = _make_mock_client(available=False)
    report = generate(variance_df, chunks, client=mock_client)
    assert report.meta.model == "fallback"


def test_masked_generation_roundtrip(variance_df) -> None:
    """Маскирование сумм + демаскирование."""
    fake = {
        "summary": "Отклонение __NUM_0001__",
        "items": [
            {
                "account": "Маркетинг",
                "period": "2025-01",
                "abs_variance": 350000.0,
                "rel_variance": 0.35,
                "hypotheses": ["Причина __NUM_0001__"],
                "references": [],
                "questions": ["Почему __NUM_0001__?"],
            }
        ],
    }
    mock_client = _make_mock_client(
        available=True,
        response=json.dumps(fake),
        model="mock",
    )

    report = generate(variance_df, [], client=mock_client, mask=True)
    assert isinstance(report, ReportJSON)


def test_number_coercion_percent_string(variance_df) -> None:
    """'3.43%' и '-5.0%' нормализуются в float."""
    fake = {
        "summary": "Резюме",
        "items": [
            {
                "account": "Маркетинг",
                "period": "2025-01",
                "abs_variance": "350 000",
                "rel_variance": "35%",
                "hypotheses": ["гипотеза"],
                "references": [],
                "questions": ["вопрос"],
            }
        ],
    }
    mock_client = _make_mock_client(
        available=True,
        response=json.dumps(fake),
        model="mock",
    )

    report = generate(variance_df, [], client=mock_client)
    assert report.items[0].abs_variance == 350000.0
    assert abs(report.items[0].rel_variance - 0.35) < 1e-9


def test_numeric_field_restored_from_df(variance_df) -> None:
    """Если LLM вернул '__NUM_xxxx__' — подставляем значение из DataFrame."""
    fake = {
        "summary": "Резюме",
        "items": [
            {
                "account": "Маркетинг",
                "period": "2025-01",
                "abs_variance": "__NUM_0003__",
                "rel_variance": "__NUM_0004__%",
                "hypotheses": ["гипотеза"],
                "references": [],
                "questions": ["вопрос"],
            }
        ],
    }
    mock_client = _make_mock_client(
        available=True,
        response=json.dumps(fake),
        model="mock",
    )

    report = generate(variance_df, [], client=mock_client)
    assert report.items[0].abs_variance == 350000.0
    assert abs(report.items[0].rel_variance - 0.35) < 1e-9