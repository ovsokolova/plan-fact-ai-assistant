"""Streamlit UI: план/факт, отклонения, графики, ЦФО, документы, записка."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import streamlit as st

from src.analyzer import aggregate_by_owner, compute
from src.charts import make_bar, make_line, make_owner_bar, make_waterfall
from src.export import export_charts_html, report_to_docx, report_to_pdf
from src.llm_agent import generate, report_to_dict, report_to_markdown
from src.loader import load
from src.logging_setup import setup_logging
from src.rag import ingest_directory, make_store, retrieve

setup_logging()

st.set_page_config(page_title="План vs Факт", page_icon="chart", layout="wide")
st.markdown(
    """
    <style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 16px; font-weight: 600; color: #1f2937;
    }
    .stTabs [data-baseweb="tab-list"] button {
        background-color: #f3f4f6; border-radius: 8px 8px 0 0;
        margin-right: 4px; padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] { background-color: #dc2626 !important; }
    .stTabs [aria-selected="true"] p { color: #ffffff !important; font-weight: 700; }
    .stTabs [data-baseweb="tab-list"] button:hover { background-color: #e5e7eb; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("План vs Факт — анализ отклонений")
st.caption("MVP: загрузка, отклонения, графики, RAG, LLM-записка")


if "rag_store" not in st.session_state:
    st.session_state.rag_store = make_store()
if "rag_indexed" not in st.session_state:
    st.session_state.rag_indexed = 0


with st.sidebar:
    st.header("Настройки")
    threshold_yellow = st.slider("Порог yellow, %", 0, 30, 5) / 100
    threshold_red = st.slider("Порог red, %", 1, 100, 15) / 100
    top_n = st.number_input("Топ-N отклонений", min_value=1, max_value=200, value=20)
    top_n_charts = st.number_input("Топ-N в графиках", min_value=1, max_value=50, value=10)

    st.divider()
    st.header("RAG")
    st.caption(f"Чанков в индексе: {st.session_state.rag_indexed}")
    mask_before_llm = st.checkbox("Маскировать суммы перед LLM", value=True)
    top_k = st.number_input("Top-K чанков", min_value=1, max_value=20, value=5)
    min_score = st.slider("Min score", 0.0, 1.0, 0.5)


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

        total_plan = float(result["plan"].sum())
        total_fact = float(result["fact"].sum())
        total_abs = float(result["abs_variance"].sum())
        total_rel = total_abs / total_plan if total_plan else None

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("План (топ-N)", f"{total_plan:,.0f}")
        m2.metric("Факт (топ-N)", f"{total_fact:,.0f}")
        m3.metric("Отклонение", f"{total_abs:+,.0f}")
        m4.metric("Отклонение, %", f"{total_rel:+.2%}" if total_rel is not None else "--")

        tab_table, tab_bar, tab_wf, tab_line, tab_owner, tab_docs, tab_report = st.tabs(
            ["Таблица", "Bar", "Waterfall", "Динамика", "ЦФО", "Документы", "Записка"]
        )

        with tab_table:
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
            csv = result.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Скачать CSV", data=csv, file_name="variance.csv", mime="text/csv")

        with tab_bar:
            st.plotly_chart(make_bar(result, top_n=int(top_n_charts)), use_container_width=True)

        with tab_wf:
            st.plotly_chart(make_waterfall(result, top_n=int(top_n_charts)), use_container_width=True)

        with tab_line:
            full_result = compute(
                df,
                threshold_yellow=threshold_yellow,
                threshold_red=threshold_red,
                top_n=len(df),
            )
            st.plotly_chart(make_line(full_result), use_container_width=True)

        with tab_owner:
            if "owner" in df.columns:
                df_owner = aggregate_by_owner(result)
                st.plotly_chart(make_owner_bar(df_owner), use_container_width=True)
                st.dataframe(
                    df_owner.style.format(
                        {
                            "plan": "{:,.0f}",
                            "fact": "{:,.0f}",
                            "abs_variance": "{:+,.0f}",
                            "rel_variance": "{:+.2%}",
                        },
                        na_rep="--",
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Нет колонки owner — разрез по ЦФО недоступен.")

        with tab_docs:
            st.subheader("Документы для RAG")
            doc_files = st.file_uploader(
                "Файлы документов",
                type=["pdf", "docx", "doc", "txt", "md"],
                accept_multiple_files=True,
                key="docs",
            )
            if st.button("Проиндексировать документы"):
                docs_dir = Path("data/docs")
                docs_dir.mkdir(parents=True, exist_ok=True)
                for f in doc_files or []:
                    target = docs_dir / Path(f.name).name
                    target.write_bytes(f.getvalue())
                with st.spinner("Индексирую..."):
                    n = ingest_directory(st.session_state.rag_store, docs_dir)
                    st.session_state.rag_indexed = st.session_state.rag_store.count()
                st.success(f"Проиндексировано: {n}. Всего: {st.session_state.rag_indexed}")

        with tab_report:
            st.subheader("Аналитическая записка")
            if st.button("Сгенерировать записку"):
                with st.spinner("Ищу контекст..."):
                    query = " ".join(result["account"].astype(str).head(5).tolist())
                    chunks = retrieve(
                        st.session_state.rag_store, query, k=int(top_k), min_score=float(min_score)
                    )
                with st.spinner("Генерирую отчёт..."):
                    report = generate(result, chunks, mask=mask_before_llm)
                md = report_to_markdown(report)
                st.markdown(md)
                st.download_button(
                    "Скачать .md", data=md.encode("utf-8"),
                    file_name="report.md", mime="text/markdown",
                )
                import json as _json
                st.download_button(
                    "Скачать .json",
                    data=_json.dumps(report_to_dict(report), ensure_ascii=False, indent=2).encode("utf-8"),
                    file_name="report.json", mime="application/json",
                )
                docx_bytes = report_to_docx(report)
                st.download_button(
                    "Скачать .docx",
                    data=docx_bytes,
                    file_name="report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

                pdf_bytes = report_to_pdf(report)
                if pdf_bytes is not None:
                    st.download_button(
                        "Скачать .pdf",
                        data=pdf_bytes,
                        file_name="report.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.caption("PDF недоступен: установите `pip install weasyprint`")
                if report.meta.model == "fallback":
                    st.warning("LLM недоступна — сгенерирован шаблонный отчёт.")
                if report.meta.masked:
                    st.info("Суммы маскированы перед отправкой в LLM.")

        # --- Экспорт графиков в HTML (кнопка в сайдбаре) ---
        with st.sidebar:
            st.divider()
            st.header("Экспорт графиков")
            if st.button("Сохранить графики в HTML"):
                charts = {
                    "bar": make_bar(result, top_n=int(top_n_charts)),
                    "waterfall": make_waterfall(result, top_n=int(top_n_charts)),
                    "line": make_line(result),
                }
                if "owner" in df.columns:
                    charts["owner"] = make_owner_bar(aggregate_by_owner(result))
                files = export_charts_html(charts, output_dir="exports/charts")
                st.success(f"Сохранено {len(files)} файлов в exports/charts/")
                for f in files:
                    st.caption(str(f))

    except FileNotFoundError as e:
        st.error(f"Файл не найден: {e}")
    except ValueError as e:
        st.error(f"Ошибка валидации: {e}")
    except Exception as e:  # noqa: BLE001
        st.exception(e)
else:
    st.info("Загрузите два файла: план и факт.")