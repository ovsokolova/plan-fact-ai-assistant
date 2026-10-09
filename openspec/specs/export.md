# Spec: Export

## Назначение
Экспорт отчёта и графиков в файлы.

## Функциональные требования
- FR-6.1 Экспорт отчёта в Markdown (report.md).
- FR-6.2 Экспорт отчёта в DOCX (report.docx).
- FR-6.3 Экспорт графиков в HTML (charts/*.html).
- FR-6.4 В report.md — YAML-front-matter с метаданными (model, generated_at, версия схемы).
- FR-6.5 Экспорт ReportJSON (report.json) для интеграций.

## Нефункциональные требования
- NFR-6.1 UTF-8, кириллица не ломается.
- NFR-6.2 Экспорт <= 3 сек для отчёта до 800 слов.

## Критерии приёмки
- AC-1 Given ReportJSON, When export md, Then файл открывается в GitHub и Word.
- AC-2 Given ReportJSON, When export docx, Then заголовки и таблицы сохранены.
- AC-3 Given charts dict, When export, Then все графики в отдельных файлах.