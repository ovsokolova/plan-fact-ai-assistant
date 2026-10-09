"""Графики для UI: bar, waterfall, line.

Соответствует openspec/specs/charts.md (FR-5.1..FR-5.6).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

COLOR_GREEN = "#28a745"
COLOR_YELLOW = "#ffc107"
COLOR_RED = "#dc3545"
COLOR_PLAN = "#6c757d"
COLOR_FACT = "#0d6efd"


def _status_color(status: str) -> str:
    return {
        "green": COLOR_GREEN,
        "yellow": COLOR_YELLOW,
        "red": COLOR_RED,
    }.get(status, COLOR_PLAN)


def make_bar(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Bar chart: план vs факт по топ-N статьям."""
    data = df.head(top_n).copy()
    labels = data["account"].astype(str) + " (" + data["period"].astype(str) + ")"

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="План",
            x=labels,
            y=data["plan"],
            marker_color=COLOR_PLAN,
            hovertemplate="%{x}<br>План: %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Факт",
            x=labels,
            y=data["fact"],
            marker_color=[
                _status_color(s) for s in data["status"]
            ],
            hovertemplate="%{x}<br>Факт: %{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        title=f"План vs Факт: топ-{min(top_n, len(data))}",
        xaxis_title="Статья",
        yaxis_title="Сумма",
        legend_title="",
        height=500,
    )
    return fig


def make_waterfall(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Waterfall: вклад статей в общее отклонение (abs_variance)."""
    data = df.head(top_n).copy()
    labels = list(data["account"].astype(str) + " (" + data["period"].astype(str) + ")")

    total = float(data["abs_variance"].sum())
    measures = ["relative"] * len(data) + ["total"]
    x = labels + ["Итого"]
    y = list(data["abs_variance"]) + [total]

    fig = go.Figure(
        go.Waterfall(
            name="Отклонение",
            orientation="v",
            measure=measures,
            x=x,
            y=y,
            text=[f"{v:+,.0f}" for v in y],
            textposition="outside",
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": COLOR_RED}},
            decreasing={"marker": {"color": COLOR_GREEN}},
            totals={"marker": {"color": COLOR_PLAN}},
        )
    )
    fig.update_layout(
        title=f"Waterfall: вклад статей в отклонение (топ-{min(top_n, len(data))})",
        yaxis_title="Отклонение (факт - план)",
        height=500,
    )
    return fig


def make_line(df: pd.DataFrame) -> go.Figure:
    """Line chart: динамика план/факт по периодам (сумма по статьям)."""
    grouped = (
        df.groupby("period", dropna=False)[["plan", "fact"]]
        .sum()
        .reset_index()
        .sort_values("period")
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            name="План",
            x=grouped["period"],
            y=grouped["plan"],
            mode="lines+markers",
            line={"color": COLOR_PLAN, "dash": "dash"},
            hovertemplate="%{x}<br>План: %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            name="Факт",
            x=grouped["period"],
            y=grouped["fact"],
            mode="lines+markers",
            line={"color": COLOR_FACT},
            hovertemplate="%{x}<br>Факт: %{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Динамика план vs факт по периодам",
        xaxis_title="Период",
        yaxis_title="Сумма",
        height=450,
    )
    return fig


def make_owner_bar(df_owner: pd.DataFrame) -> go.Figure:
    """Bar chart: отклонения по ЦФО (owner)."""
    data = df_owner.copy()
    fig = go.Figure(
        go.Bar(
            x=data["owner"].astype(str),
            y=data["abs_variance"],
            marker_color=[
                COLOR_RED if v > 0 else COLOR_GREEN for v in data["abs_variance"]
            ],
            text=[f"{v:+,.0f}" for v in data["abs_variance"]],
            textposition="outside",
            hovertemplate="%{x}<br>Отклонение: %{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Отклонения по ЦФО",
        xaxis_title="ЦФО",
        yaxis_title="Отклонение (факт - план)",
        height=450,
    )
    return fig