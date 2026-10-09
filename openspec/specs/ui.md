# Spec: Streamlit UI

## Назначение
Интерфейс для загрузки данных, просмотра отклонений, генерации отчёта и чата.

## Экраны

### S-1. Загрузка данных
- Два file_uploader: план и факт (.xlsx/.csv).
- Кнопка «Загрузить пример» — подставляет data/examples/*.
- Валидация: показать ошибки из loader.

### S-2. Сводная таблица
- st.dataframe с колонками: account, period, plan, fact, abs, rel, status.
- Цветовая подсветка status (green/yellow/red).
- Фильтры: период, owner, порог |rel|.

### S-3. Графики
- Bar: план vs факт по топ-N.
- Waterfall: вклад статей в общее отклонение.
- Line: динамика по периодам.

### S-4. Отчёт
- Кнопка «Сгенерировать записку».
- Прогресс (индексация RAG -> LLM -> рендер).
- Отображение markdown + кнопка «Скачать .md».

### S-5. Чат
- st.chat_input + st.chat_message.
- Контекст: последний variance_df + retrieved chunks.

### S-6. Настройки (sidebar)
- LLM_PROVIDER, LLM_MODEL, TOP_K, MIN_SCORE.
- Кнопка «Переиндексировать RAG».

## Критерии приёмки
- AC-1 Given корректные файлы, When загрузка, Then таблица отклонений на S-2.
- AC-2 Given пустой data/docs, When генерация, Then отчёт без ссылок, warning.
- AC-3 Given нажатие «Скачать», Then отдаётся .md с ReportJSON внутри как комментарий.