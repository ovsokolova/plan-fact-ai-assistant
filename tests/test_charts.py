from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from src.charts import make_bar, make_line, make_owner_bar, make_waterfall


@pytest.fixture
def variance_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account": ["Маркетинг", "Логистика", "ФОТ"],
            "period": ["2025-01", "2025-01", "2025-01"],
            "plan": [1_000_000.0, 800_000.0, 3_500_000.0],
            "fact": [1_350_000.0, 760_000.0, 3_620_000.0],
            "abs_variance": [350_000.0, -40_000.0, 120_000.0],
            "rel_variance": [0.35, -0.05, 0.0343],
            "status": ["red", "green", "green"],
            "owner": ["CMO", "COO", "HRD"],
        }
    )


@pytest.fixture
def empty_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "account",
            "period",
            "plan",
            "fact",
            "abs_variance",
            "rel_variance",
            "status",
            "owner",
        ]
    )


def test_make_bar_returns_figure(variance_df: pd.DataFrame) -> None:
    fig = make_bar(variance_df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_make_waterfall_returns_figure(variance_df: pd.DataFrame) -> None:
    fig = make_waterfall(variance_df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].measure[-1] == "total"


def test_make_line_single_period(variance_df: pd.DataFrame) -> None:
    fig = make_line(variance_df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_make_owner_bar(variance_df: pd.DataFrame) -> None:
    from src.analyzer import aggregate_by_owner

    df_owner = aggregate_by_owner(variance_df)
    fig = make_owner_bar(df_owner)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


# --- Edge cases ---


def test_make_bar_empty(empty_df: pd.DataFrame) -> None:
    fig = make_bar(empty_df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_make_waterfall_empty(empty_df: pd.DataFrame) -> None:
    fig = make_waterfall(empty_df)
    assert isinstance(fig, go.Figure)


def test_make_line_empty(empty_df: pd.DataFrame) -> None:
    fig = make_line(empty_df)
    assert isinstance(fig, go.Figure)


def test_make_line_two_periods() -> None:
    df = pd.DataFrame(
        {
            "account": ["A", "A"],
            "period": ["2025-01", "2025-02"],
            "plan": [100.0, 200.0],
            "fact": [110.0, 180.0],
            "abs_variance": [10.0, -20.0],
            "rel_variance": [0.1, -0.1],
            "status": ["yellow", "yellow"],
        }
    )
    fig = make_line(df)
    assert isinstance(fig, go.Figure)
    # 2 trace: план и факт
    assert len(fig.data) == 2
    # в каждом trace по 2 точки
    assert len(fig.data[0].x) == 2