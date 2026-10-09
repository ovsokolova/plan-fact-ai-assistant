"""Загрузка и нормализация плана/факта из Excel/CSV.

Соответствует openspec/specs/data-ingestion.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd

PLAN_REQUIRED: Final[frozenset[str]] = frozenset({"account", "period", "plan"})
FACT_REQUIRED: Final[frozenset[str]] = frozenset({"account", "period", "fact"})
SUPPORTED_SUFFIXES: Final[tuple[str, ...]] = (".xlsx", ".xls", ".csv")


def _read_table(path: Path, sheet: str | None, encoding: str) -> pd.DataFrame:
    """Читает файл и возвращает один DataFrame.

    Для Excel: если sheet=None, читает первый лист (а не все сразу, чтобы
    не получить dict).
    """
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Неподдерживаемый формат: {suffix}. Ожидается один из: {SUPPORTED_SUFFIXES}"
        )
    if suffix == ".csv":
        return pd.read_csv(path, encoding=encoding)

    # sheet_name=None возвращает dict всех листов — берём первый лист,
    # если конкретный не указан.
    effective_sheet = sheet if sheet is not None else 0
    df = pd.read_excel(path, sheet_name=effective_sheet)
    if isinstance(df, dict):  # на всякий случай, если pandas вернёт dict
        df = next(iter(df.values()))
    return df


def _validate_schema(df: pd.DataFrame, required: frozenset[str], source: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{source}: отсутствуют колонки: {sorted(missing)}")


def _validate_dtypes(df: pd.DataFrame, value_cols: tuple[str, ...], source: str) -> pd.DataFrame:
    out = df.copy()
    for col in value_cols:
        try:
            out[col] = pd.to_numeric(out[col], errors="raise")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{source}: колонка {col} содержит нечисловые значения") from exc
    if "owner" in out.columns:
        out["owner"] = out["owner"].astype("string")
    out["account"] = out["account"].astype("string")
    out["period"] = out["period"].astype("string")
    return out


def _validate_unique(df: pd.DataFrame, source: str) -> None:
    key = ["account", "period"]
    dupes = df[df.duplicated(subset=key, keep=False)]
    if not dupes.empty:
        preview = dupes[key].drop_duplicates().head(10).to_dict("records")
        raise ValueError(f"{source}: дубли по ключу {key}: {preview}")


def load(
    plan_path: str | Path,
    fact_path: str | Path,
    *,
    plan_sheet: str | int | None = None,
    fact_sheet: str | int | None = None,
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """Загружает план и факт, объединяет по ключу (account, period).

    Returns:
        DataFrame с колонками: account, period, plan, fact, owner (optional).
    """
    plan_path = Path(plan_path)
    fact_path = Path(fact_path)

    plan_df = _read_table(plan_path, plan_sheet, encoding)
    fact_df = _read_table(fact_path, fact_sheet, encoding)

    _validate_schema(plan_df, PLAN_REQUIRED, f"план ({plan_path.name})")
    _validate_schema(fact_df, FACT_REQUIRED, f"факт ({fact_path.name})")

    plan_df = _validate_dtypes(plan_df, ("plan",), f"план ({plan_path.name})")
    fact_df = _validate_dtypes(fact_df, ("fact",), f"факт ({fact_path.name})")

    _validate_unique(plan_df, f"план ({plan_path.name})")
    _validate_unique(fact_df, f"факт ({fact_path.name})")

    # Убираем лишние колонки, оставляем только нужные
    plan_cols = ["account", "period", "plan"]
    if "owner" in plan_df.columns:
        plan_cols.append("owner")
    plan_df = plan_df[plan_cols]

    fact_df = fact_df[["account", "period", "fact"]]

    merged = plan_df.merge(
        fact_df, on=["account", "period"], how="outer", suffixes=("_plan", "_fact")
    )
    merged["plan"] = merged["plan"].fillna(0)
    merged["fact"] = merged["fact"].fillna(0)

    cols = ["account", "period", "plan", "fact"]
    if "owner" in merged.columns:
        cols.append("owner")

    return merged[cols].reset_index(drop=True)