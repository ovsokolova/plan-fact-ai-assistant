from __future__ import annotations

import pandas as pd
import pytest

from src.llm_agent import (
    LLMClient,
    LLMConfig,
    ReportJSON,
    generate,
    report_to_dict,
    report_to_markdown,
)
from src.rag import Chunk


@pytest.fixture
def variance_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account": ["Маркетинг", "Логистика"],
            "period": ["2025-01", "2025-01"],
            "plan": [1_000_000.0, 800_000.0],
            "fact": [1_350_000.0, 760_000.0],
            "abs_variance": [350_000.0, -40_000.0],
            "rel_variance": [0.35, -0.05],
            "status": ["red", "green"],
            "owner": ["CMO", "COO"],
        }
    )


@pytest.fixture
def chunks() -> list[Chunk]:
    return [
        Chunk(
            text="Оплата производится авансом 100%",
            source="contract_45_2024.pdf",
            page=2,
            clause="4.2",
            score=0.9,
        )
    ]


def test_client_unavailable_without_key() -> None:
    cfg = LLMConfig(provider="openai", api_key=None)
    client = LLMClient(cfg)
    assert client.available() is False


def test_generate_fallback_without_llm(
    variance_df: pd.DataFrame, chunks: list[Chunk], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = generate(variance_df, chunks)
    assert isinstance(report, ReportJSON)
    assert report.meta.model == "fallback"
    assert len(report.items) == 2


def test_fallback_contains_questions(variance_df: pd.DataFrame) -> None:
    report = generate(variance_df, [])
    for item in report.items:
        assert len(item.questions) >= 1
        assert len(item.hypotheses) >= 1


def test_report_to_markdown(variance_df: pd.DataFrame) -> None:
    report = generate(variance_df, [])
    md = report_to_markdown(report)
    assert "# Аналитическая записка" in md
    assert "## Резюме" in md
    assert "Маркетинг" in md


def test_report_to_dict(variance_df: pd.DataFrame) -> None:
    report = generate(variance_df, [])
    d = report_to_dict(report)
    assert "summary" in d
    assert "items" in d
    assert d["meta"]["model"] == "fallback"


def test_report_schema_validation() -> None:
    with pytest.raises(Exception):
        ReportJSON.model_validate({"items": []})


def test_max_items_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    df = pd.DataFrame(
        {
            "account": [f"A{i}" for i in range(20)],
            "period": ["2025-01"] * 20,
            "plan": [100.0] * 20,
            "fact": [110.0] * 20,
            "abs_variance": [10.0] * 20,
            "rel_variance": [0.1] * 20,
            "status": ["yellow"] * 20,
        }
    )
    report = generate(df, [], max_items=5)
    assert len(report.items) == 5