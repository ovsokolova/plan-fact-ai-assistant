# Tasks: plan-fact-ai-assistant

Легенда: [ ] todo · [~] in progress · [x] done · [!] blocked

## Эпик 0. Bootstrap
- [x] init repo, .gitignore, README
- [ ] requirements.txt / pyproject.toml
- [ ] .env.example
- [ ] pre-commit: ruff, black
- [ ] CI: GitHub Actions (lint + pytest)

## Эпик 1. Data Ingestion
- [ ] loader.py: чтение xlsx/csv
- [ ] нормализация схемы
- [ ] валидация обязательных колонок
- [ ] обработка дублей
- [ ] unit-тесты AC-1..AC-3
- [ ] фикстуры: data/examples/plan.xlsx, fact.xlsx

## Эпик 2. Variance Analysis
- [ ] compute(): abs/rel variance
- [ ] светофор
- [ ] топ-N по модулю и по %
- [ ] агрегация по owner и period
- [ ] unit-тесты AC-1..AC-3

## Эпик 3. RAG
- [ ] загрузка PDF/DOCX
- [ ] чанкинг с метаданными
- [ ] эмбеддинги (OpenAI + e5)
- [ ] Chroma backend
- [ ] FAISS backend
- [ ] retrieve() c top-k и min_score
- [ ] integration-тесты AC-1..AC-3

## Эпик 4. LLM Report
- [ ] LLMClient (OpenAI)
- [ ] LLMClient (Ollama)
- [ ] промпт под JSON-mode
- [ ] Pydantic-схема ReportJSON
- [ ] retry при невалидном JSON
- [ ] fallback-шаблон
- [ ] eval-набор из 10 кейсов

## Эпик 5. Charts
- [ ] план vs факт (bar)
- [ ] waterfall по топ-N
- [ ] динамика по периодам
- [ ] экспорт в HTML

## Эпик 6. UI
- [ ] загрузка файлов
- [ ] таблица отклонений
- [ ] графики
- [ ] панель отчёта
- [ ] чат с уточнениями
- [ ] настройки

## Эпик 7. Отчёт и экспорт
- [ ] report.render() -> markdown
- [ ] экспорт DOCX
- [ ] экспорт PDF
- [ ] ReportJSON -> JSON Schema

## Эпик 8. Качество и безопасность
- [ ] маскирование сумм перед OpenAI
- [ ] логи без сумм/PII
- [ ] тесты на утечки
- [ ] README: раздел privacy

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