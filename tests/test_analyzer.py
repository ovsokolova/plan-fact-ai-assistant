from __future__ import annotations

import pandas as pd

from src.analyzer import STATUS_GREEN, STATUS_RED, compute


def _df(plan: float, fact: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account": ["X"],
            "period": ["2025-01"],
            "plan": [plan],
            "fact": [fact],
        }
    )


def test_abs_variance_positive() -> None:
    out = compute(_df(1_000_000, 1_350_000))
    assert out["abs_variance"].iloc[0] == 350_000
    assert round(out["rel_variance"].iloc[0], 4) == 0.35
    assert out["status"].iloc[0] == STATUS_RED


def test_rel_variance_zero_plan() -> None:
    out = compute(_df(0, 100))
    assert pd.isna(out["rel_variance"].iloc[0])
    assert out["status"].iloc[0] == STATUS_RED


def test_status_green() -> None:
    out = compute(_df(1_000_000, 1_030_000))
    assert out["status"].iloc[0] == STATUS_GREEN