"""Расчёт отклонений план vs факт.

Соответствует openspec/specs/variance-analysis.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

STATUS_GREEN = "green"
STATUS_YELLOW = "yellow"
STATUS_RED = "red"


def _status(rel: float | None, yellow: float, red: float) -> str:
    if rel is None or pd.isna(rel):
        return STATUS_RED
    a = abs(rel)
    if a <= yellow:
        return STATUS_GREEN
    if a <= red:
        return STATUS_YELLOW
    return STATUS_RED


def compute(
    df: pd.DataFrame,
    *,
    threshold_yellow: float = 0.05,
    threshold_red: float = 0.15,
    top_n: int = 10,
) -> pd.DataFrame:
    """Считает abs/rel отклонения, светофор, ранжирует по модулю abs."""
    required = {"account", "period", "plan", "fact"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Не хватает колонок: {sorted(missing)}")

    out = df.copy()
    out["abs_variance"] = out["fact"] - out["plan"]

    plan_nonzero = out["plan"].replace(0, np.nan)
    out["rel_variance"] = (out["fact"] - out["plan"]) / plan_nonzero

    out["status"] = out["rel_variance"].apply(
        lambda r: _status(r, threshold_yellow, threshold_red)
    )

    out = out.reindex(out["abs_variance"].abs().sort_values(ascending=False).index).head(top_n)

    cols = ["account", "period", "plan", "fact", "abs_variance", "rel_variance", "status"]
    if "owner" in out.columns:
        cols.append("owner")

    return out[cols].reset_index(drop=True)


def aggregate_by_owner(df: pd.DataFrame) -> pd.DataFrame:
    """Агрегация отклонений по ЦФО."""
    if "owner" not in df.columns:
        raise ValueError("Нет колонки owner")
    grouped = (
        df.groupby("owner", dropna=False)[["plan", "fact", "abs_variance"]].sum().reset_index()
    )
    plan_nonzero = grouped["plan"].replace(0, np.nan)
    grouped["rel_variance"] = (grouped["fact"] - grouped["plan"]) / plan_nonzero
    return grouped