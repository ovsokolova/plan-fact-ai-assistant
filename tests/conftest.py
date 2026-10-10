"""Общие фикстуры для тестов."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    d = Path(__file__).parent / "fixtures"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def plan_valid(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "plan_valid.xlsx"
    pd.DataFrame(
        {
            "account": ["Маркетинг", "Логистика", "ФОТ"],
            "period": ["2025-01", "2025-01", "2025-01"],
            "plan": [1_000_000.0, 800_000.0, 3_500_000.0],
            "owner": ["CMO", "COO", "HRD"],
        }
    ).to_excel(path, index=False)
    return path


@pytest.fixture
def fact_valid(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "fact_valid.xlsx"
    pd.DataFrame(
        {
            "account": ["Маркетинг", "Логистика", "ФОТ"],
            "period": ["2025-01", "2025-01", "2025-01"],
            "fact": [1_350_000.0, 760_000.0, 3_620_000.0],
        }
    ).to_excel(path, index=False)
    return path


@pytest.fixture
def plan_bad_schema(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "plan_bad_schema.xlsx"
    pd.DataFrame(
        {
            "account": ["Маркетинг"],
            "period": ["2025-01"],
            "plan": [1_000_000.0],
        }
    ).to_excel(path, index=False)
    return path


@pytest.fixture
def plan_csv(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "plan_valid.csv"
    pd.DataFrame(
        {
            "account": ["Маркетинг", "Логистика", "ФОТ"],
            "period": ["2025-01", "2025-01", "2025-01"],
            "plan": [1_000_000.0, 800_000.0, 3_500_000.0],
            "owner": ["CMO", "COO", "HRD"],
        }
    ).to_csv(path, index=False, encoding="utf-8")
    return path


@pytest.fixture
def fact_csv(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "fact_valid.csv"
    pd.DataFrame(
        {
            "account": ["Маркетинг", "Логистика", "ФОТ"],
            "period": ["2025-01", "2025-01", "2025-01"],
            "fact": [1_350_000.0, 760_000.0, 3_620_000.0],
        }
    ).to_csv(path, index=False, encoding="utf-8")
    return path
