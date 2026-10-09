# Test Plan: plan-fact-ai-assistant

## 1. Уровни тестирования

| Уровень | Что | Инструменты |
|---|---|---|
| Unit | loader, analyzer, report.render | pytest |
| Integration | rag + llm_agent + report | pytest, фейковый LLM |
| E2E | Streamlit через Playwright | playwright |
| Eval (LLM) | качество отчёта на 10 кейсах | pytest + LLM-as-judge |

## 2. Unit-тесты по спекам

### data-ingestion
- test_load_xlsx_valid
- test_load_csv_cp1251
- test_missing_fact_column_raises
- test_duplicate_key_raises

### variance-analysis
- test_abs_variance_positive
- test_rel_variance_zero_plan
- test_status_thresholds
- test_top_n_sorted

### llm-report
- test_report_json_schema_validation
- test_fallback_on_llm_error
- test_no_hallucinated_references

### rag-retrieval
- test_chunk_metadata
- test_empty_index_returns_empty
- test_top_k_limit

## 3. Fixtures
- tests/fixtures/plan_valid.xlsx
- tests/fixtures/fact_valid.xlsx
- tests/fixtures/plan_bad_schema.xlsx
- tests/fixtures/docs/contract_45_2024.pdf

## 4. Eval (LLM)
Кейсы:
1. Отклонение 35% + есть договор -> должна быть ссылка.
2. Отклонение 3% -> не должно быть в топ-N.
3. Нет документов -> отчёт без ссылок.

Метрики: precision/recall ссылок, отсутствие выдуманных пунктов.

## 5. CI
- На push/PR: ruff, black --check, pytest --cov.
- Порог покрытия: >= 70%.