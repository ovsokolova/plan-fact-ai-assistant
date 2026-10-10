# Tasks: plan-fact-ai-assistant

Легенда: [ ] todo · [~] in progress · [x] done · [!] blocked

## Эпик 0. Bootstrap
- [x] init repo, .gitignore, README
- [ ] requirements.txt / pyproject.toml
- [ ] .env.example
- [x] pre-commit: ruff, black
- [x] CI: GitHub Actions (lint + pytest)

## Эпик 1. Data Ingestion
- [x] loader.py: чтение xlsx/csv
- [x] нормализация схемы
- [x] валидация обязательных колонок
- [x] обработка дублей
- [x] unit-тесты AC-1..AC-3
- [x] фикстуры: tests/conftest.py

## Эпик 2. Variance Analysis
- [x] compute(): abs/rel variance
- [x] светофор
- [x] топ-N по модулю и по %
- [x] агрегация по owner и period
- [x] unit-тесты AC-1..AC-3

## Эпик 3. RAG
- [ ] загрузка PDF/DOCX
- [x] чанкинг с метаданными
- [~] эмбеддинги (Chroma default; e5 — TODO)
- [x] Chroma backend
- [ ] FAISS backend
- [x] retrieve() c top-k и min_score
- [x] integration-тесты AC-1..AC-3

## Эпик 4. LLM Report
- [x] LLMClient (OpenAI)
- [x] LLMClient (Ollama)
- [x] промпт под JSON-mode
- [x] Pydantic-схема ReportJSON
- [~] retry при невалидном JSON (fallback есть)
- [ ] fallback-шаблон
- [~] eval-набор (интеграционные тесты есть)

## Эпик 5. Charts (spec: charts)
- [x] план vs факт (bar)
- [x] waterfall по топ-N
- [x] динамика по периодам
- [x] экспорт в HTML

## Эпик 6. UI (spec: ui)
- [x] загрузка файлов
- [x] таблица отклонений
- [x] графики (5 вкладок)
- [~] панель отчёта (CSV-экспорт)
- [ ] чат с уточнениями
- [ ] настройки

## Эпик 7. Отчёт и экспорт (spec: export)
- [ ] report.render() -> markdown
- [x] экспорт DOCX
- [x] экспорт PDF (WeasyPrint, soft-import)
- [ ] ReportJSON -> JSON Schema

## Эпик 8. Качество и безопасность
- [ ] маскирование сумм перед OpenAI
- [x] логи без сумм/PII (SanitizingFormatter)
- [ ] тесты на утечки
- [~] README: раздел privacy (в roadmap)

## Эпик 9. Docs
- [x] openspec/proposal.md
- [x] openspec/specs/*
- [x] openspec/design.md
- [x] openspec/adr/*
- [x] openspec/api-contract.md
- [x] openspec/tasks.md
- [ ] README: ссылки на openspec

## Эпик 10. Roadmap
- [ ] 1С-выгрузки
- [ ] мультипериодный анализ
- [ ] алерты Telegram/Slack
- [ ] роли и права
- [ ] OCR сканов