# ADR-0004: Контракт отчёта — структурированный JSON

- Статус: Accepted
- Дата: 2026-10-09

## Решение
LLM возвращает строгий JSON по схеме ReportJSON. Рендер в markdown — отдельный слой report.render.

```json
{
  "summary": "string",
  "items": [
    {
      "account": "string",
      "period": "YYYY-MM",
      "abs_variance": 0,
      "rel_variance": 0.0,
      "hypotheses": ["string"],
      "references": [
        {"source": "string", "page": 0, "clause": "string", "quote": "string"}
      ],
      "questions": ["string"]
    }
  ],
  "meta": {"model": "string", "generated_at": "ISO8601"}
}
```

## Обоснование
- Отделение смысла от представления.
- Валидация через Pydantic.
- Упрощает тестирование.
- Ссылки на источники — first-class.

## Альтернативы
| Вариант | Почему нет |
|---|---|
| Свободный markdown | Нестабильно |
| HTML | Тяжело тестировать |
| Plain text | Нет структуры |

## Последствия
- Плюс: надёжность и тестируемость.
- Минус: промпт под JSON-mode + retry.