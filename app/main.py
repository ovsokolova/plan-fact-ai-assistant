"""Streamlit UI: загрузка плана/факта, таблица отклонений.

MVP без LLM и RAG — только математика.
Соответствует openspec/specs/ui.md (S-1, S-2).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.analyzer import compute
from src.loader import load

st.set_page_config(page_title="План vs Факт", page_icon="chart", layout="wide")
st.title("План vs Факт — анализ отклонений")
st.caption("MVP: загрузка Excel/CSV, расчёт отклонений, сводная таблица")

with st.sidebar:
    st.header("Настройки")
    threshold_yellow = st.slider("Порог yellow, %", 0, 30, 5) / 100
    threshold_red = st.slider("Порог red, %", 1, 100, 15) / 100
    top_n = st.number_input("Топ-N отклонений", min_value=1, max_value=200, value=20)

col1, col2 = st.columns(2)
with col1:
    plan_file = st.file_uploader("План (.xlsx/.csv)", type=["xlsx", "xls", "csv"], key="plan")
with col2:
    fact_file = st.file_uploader("Факт (.xlsx/.csv)", type=["xlsx", "xls", "csv"], key="fact")


def _save_upload(uploaded) -> Path:
    tmp_dir = Path(".streamlit_tmp")
    tmp_dir.mkdir(exist_ok=True)
    name = Path(uploaded.name).name
    path = tmp_dir / name
    path.write_bytes(uploaded.getvalue())
    return path


if plan_file and fact_file:
    try:
        with st.spinner("Читаю файлы..."):
            plan_path = _save_upload(plan_file)
            fact_path = _save_upload(fact_file)
            df = load(plan_path, fact_path)

        st.success(f"Загружено строк: {len(df)}")

        with st.spinner("Считаю отклонения..."):
            result = compute(
                df,
                threshold_yellow=threshold_yellow,
                threshold_red=threshold_red,
                top_n=int(top_n),
            )

        st.subheader("Сводная таблица отклонений")


        def _highlight(row: pd.Series) -> list[str]:
            color = {
                "green": "background-color: #d4edda",
                "yellow": "background-color: #fff3cd",
                "red": "background-color: #f8d7da",
            }.get(row.get("status"), "")
            return [color] * len(row)


        styled = result.style.apply(_highlight, axis=1).format(
            {
                "plan": "{:,.0f}",
                "fact": "{:,.0f}",
                "abs_variance": "{:+,.0f}",
                "rel_variance": "{:+.2%}",
            },
            na_rep="--",
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        total_plan = float(result["plan"].sum())
        total_fact = float(result["fact"].sum())
        total_abs = float(result["abs_variance"].sum())
        total_rel = total_abs / total_plan if total_plan else None

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("План (топ-N)", f"{total_plan:,.0f}")
        m2.metric("Факт (топ-N)", f"{total_fact:,.0f}")
        m3.metric("Отклонение", f"{total_abs:+,.0f}")
        m4.metric("Отклонение, %", f"{total_rel:+.2%}" if total_rel is not None else "--")

        csv = result.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Скачать CSV",
            data=csv,
            file_name="variance.csv",
            mime="text/csv",
        )

    except FileNotFoundError as e:
        st.error(f"Файл не найден: {e}")
    except ValueError as e:
        st.error(f"Ошибка валидации данных: {e}")
    except Exception as e:  # noqa: BLE001
        st.exception(e)
else:
    st.info("Загрузите два файла: план и факт.")
    with st.expander("Формат файлов"):
        st.markdown(
            "- План: колонки account, period, plan, owner (опционально)\n"
            "- Факт: колонки account, period, fact\n"
            "- Объединение по ключу (account, period)"
        )