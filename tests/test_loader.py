from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.loader import load


def test_load_xlsx_valid(plan_valid: Path, fact_valid: Path) -> None:
    df = load(plan_valid, fact_valid)
    assert list(df.columns) == ["account", "period", "plan", "fact", "owner"]
    assert len(df) == 3
    assert df.loc[df["account"] == "Маркетинг", "fact"].iloc[0] == 1_350_000.0


def test_load_csv_valid(tmp_path: Path) -> None:
    plan = tmp_path / "plan.csv"
    fact = tmp_path / "fact.csv"
    pd.DataFrame(
        {"account": ["A", "B"], "period": ["2025-01", "2025-01"], "plan": [100.0, 200.0]}
    ).to_csv(plan, index=False, encoding="utf-8")
    pd.DataFrame(
        {"account": ["A", "B"], "period": ["2025-01", "2025-01"], "fact": [110.0, 190.0]}
    ).to_csv(fact, index=False, encoding="utf-8")

    df = load(plan, fact)
    assert list(df.columns) == ["account", "period", "plan", "fact"]
    assert len(df) == 2
    assert df["fact"].sum() == 300.0


def test_load_csv_cp1251(tmp_path: Path) -> None:
    plan = tmp_path / "plan_cp.csv"
    fact = tmp_path / "fact_cp.csv"
    pd.DataFrame(
        {"account": ["Маркетинг"], "period": ["2025-01"], "plan": [1000.0]}
    ).to_csv(plan, index=False, encoding="cp1251")
    pd.DataFrame(
        {"account": ["Маркетинг"], "period": ["2025-01"], "fact": [1100.0]}
    ).to_csv(fact, index=False, encoding="cp1251")

    df = load(plan, fact, encoding="cp1251")
    assert df["account"].iloc[0] == "Маркетинг"


def test_missing_fact_column_raises(plan_bad_schema: Path, plan_valid: Path) -> None:
    with pytest.raises(ValueError, match="отсутствуют колонки"):
        load(plan_bad_schema, plan_valid)


def test_file_not_found(tmp_path: Path, plan_valid: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "nope.xlsx", plan_valid)


def test_duplicate_key_raises(tmp_path: Path) -> None:
    plan = tmp_path / "plan_dup.xlsx"
    fact = tmp_path / "fact_dup.xlsx"
    pd.DataFrame(
        {"account": ["A", "A"], "period": ["2025-01", "2025-01"], "plan": [100.0, 200.0]}
    ).to_excel(plan, index=False)
    pd.DataFrame(
        {"account": ["A"], "period": ["2025-01"], "fact": [100.0]}
    ).to_excel(fact, index=False)

    with pytest.raises(ValueError, match="дубли"):
        load(plan, fact)