"""LLM-агент: генерация аналитической записки.

Поддерживает провайдеры: yandex (YandexGPT), ollama, openai.
Соответствует openspec/specs/llm-report.md и ADR-0001, ADR-0004.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from src.mask import Masker
from src.rag import Chunk


# ---------------------------------------------------------------------------
# Pydantic-схема отчёта (ADR-0004)
# ---------------------------------------------------------------------------


def _parse_number(v: Any) -> float | None:
    """Превращает '3.43%', '__NUM_0003__', '1 000,50' в float.

    Возвращает None если значение не парсится.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip()
    if not s:
        return None

    # Плейсхолдер маскирования вида __NUM_0003__ — не число, пропускаем
    if re.fullmatch(r"__NUM_\d+__", s):
        return None

    # Убираем %, пробелы, неразрывные пробелы
    is_percent = "%" in s
    s = s.replace("%", "").replace(" ", "").replace("\u00a0", "")

    # Убираем запятые-разделители тысяч и меняем запятую-десятичную на точку
    if "," in s and "." in s:
        s = s.replace(",", "")  # 1,234.56 -> 1234.56
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")  # 3,43 -> 3.43
        else:
            s = s.replace(",", "")   # 1,234 -> 1234

    # Оставляем только цифры, точку и минус
    s = re.sub(r"[^\d.\-]", "", s)

    try:
        val = float(s)
    except ValueError:
        return None

    if is_percent:
        val = val / 100.0
    return val


class Reference(BaseModel):
    source: str
    page: int | None = None
    clause: str | None = None
    quote: str = ""


class ReportItem(BaseModel):
    account: str
    period: str
    abs_variance: float | None = None
    rel_variance: float | None = None
    hypotheses: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)

    @field_validator("abs_variance", "rel_variance", mode="before")
    @classmethod
    def _coerce_number(cls, v: Any) -> float | None:
        return _parse_number(v)


class ReportMeta(BaseModel):
    model: str
    generated_at: str
    masked: bool = False


class ReportJSON(BaseModel):
    summary: str
    items: list[ReportItem] = Field(default_factory=list)
    meta: ReportMeta


SYSTEM_PROMPT = """Ты — финансовый аналитик. Пиши краткие аналитические записки по отклонениям план/факт для руководства.

Правила:
1. Русский язык, деловой стиль.
2. Для каждого отклонения формулируй 2-4 гипотезы причин.
3. Если есть фрагменты документов — ссылайся на них с указанием источника и пункта. Цитируй точно.
4. НЕ выдумывай ссылки и пункты. Если связи с документом нет — references пустой, гипотезы — предположения.
5. Задавай ответственным конкретные уточняющие вопросы.
6. Ответ — СТРОГО валидный JSON без markdown-обёртки, по схеме ниже.
7. Числовые поля abs_variance и rel_variance передавай ТОЛЬКО как числа (без %, без пробелов):
   - abs_variance: абсолютное отклонение в рублях, например 350000 или -40000
   - rel_variance: относительное отклонение в долях (НЕ в процентах), например 0.35 или -0.05
   НЕ добавляй символ % и НЕ используй строки.

{
  "summary": "...",
  "items": [
    {
      "account": "...",
      "period": "YYYY-MM",
      "abs_variance": 0.0,
      "rel_variance": 0.0,
      "hypotheses": ["..."],
      "references": [{"source": "...", "page": 1, "clause": "4.2", "quote": "..."}],
      "questions": ["..."]
    }
  ]
}
"""


def _build_user_prompt(variance_df: pd.DataFrame, chunks: list[Chunk]) -> str:
    lines: list[str] = ["Отклонения план/факт (топ-N):"]
    for _, row in variance_df.iterrows():
        rel = row.get("rel_variance")
        rel_str = f"{rel:+.2%}" if rel is not None and pd.notna(rel) else "n/a"
        lines.append(
            f"- {row['account']} ({row['period']}): план={row['plan']:,.0f}, "
            f"факт={row['fact']:,.0f}, отклонение={row['abs_variance']:+,.0f} ({rel_str})"
        )

    lines.append("")
    lines.append("Релевантные фрагменты документов:")
    if not chunks:
        lines.append("(нет релевантных фрагментов)")
    else:
        for i, c in enumerate(chunks, 1):
            clause = f", п. {c.clause}" if c.clause else ""
            page = f", стр. {c.page}" if c.page else ""
            lines.append(f"[{i}] {c.source}{clause}{page} (score={c.score:.2f}):")
            lines.append(c.text)
            lines.append("")

    lines.append("Сформируй аналитическую записку в формате JSON.")
    return "\n".join(lines)


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 60
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> LLMConfig:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()

        if provider == "yandex":
            return cls(
                provider="yandex",
                model=os.getenv("YANDEX_MODEL", "yandexgpt"),
                api_key=os.getenv("YANDEX_API_KEY"),
                base_url=os.getenv("YANDEX_FOLDER_ID"),
                timeout=int(os.getenv("YANDEX_TIMEOUT", "90")),
                temperature=float(os.getenv("YANDEX_TEMPERATURE", "0.1")),
            )

        if provider == "ollama":
            return cls(
                provider="ollama",
                model=os.getenv("LLM_MODEL", "llama3.2:3b"),
                api_key=None,
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                timeout=int(os.getenv("LLM_TIMEOUT", "120")),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
            )

        return cls(
            provider=provider,
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            timeout=int(os.getenv("LLM_TIMEOUT", "60")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        )


class LLMClient:
    """Обёртка над YandexGPT, Ollama или OpenAI-совместимым API."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()

    def available(self) -> bool:
        p = self.config.provider
        if p == "ollama":
            return bool(self.config.base_url)
        if p == "yandex":
            return bool(self.config.api_key and self.config.base_url)
        return bool(self.config.api_key)

    def complete(self, system: str, user: str) -> str:
        if not self.available():
            raise RuntimeError(
                f"LLM не сконфигурирован: provider={self.config.provider}, "
                f"api_key={'set' if self.config.api_key else 'missing'}, "
                f"base_url={self.config.base_url!r}"
            )

        # --- YandexGPT ---
        if self.config.provider == "yandex":
            import requests

            folder_id = self.config.base_url
            api_key = self.config.api_key
            url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Api-Key {api_key}",
            }
            model_uri = f"gpt://{folder_id}/{self.config.model}/latest"
            body = {
                "modelUri": model_uri,
                "completionOptions": {
                    "stream": False,
                    "temperature": self.config.temperature,
                    "maxTokens": 2000,
                },
                "messages": [
                    {"role": "system", "text": system},
                    {"role": "user", "text": user},
                ],
            }
            r = requests.post(url, headers=headers, json=body, timeout=self.config.timeout)
            r.raise_for_status()
            data = r.json()
            return data["result"]["alternatives"][0]["message"]["text"]

        # --- Ollama ---
        if self.config.provider == "ollama":
            import requests

            base = (self.config.base_url or "http://localhost:11434").rstrip("/")
            r = requests.post(
                f"{base}/api/chat",
                json={
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {"temperature": self.config.temperature},
                    "format": "json",
                },
                timeout=self.config.timeout,
            )
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")

        # --- OpenAI ---
        from openai import OpenAI

        kwargs: dict[str, Any] = {
            "api_key": self.config.api_key or "not-needed",
            "timeout": self.config.timeout,
        }
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url

        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


def _extract_json(text: str) -> dict[str, Any]:
    """Извлекает JSON из ответа LLM (терпим к markdown и тексту вокруг)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Пустой ответ от LLM")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    if start != -1:
        depth = 0
        in_str = False
        esc = False
        end_idx = -1
        for i in range(start, len(text)):
            ch = text[i]
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx != -1:
            try:
                return json.loads(text[start : end_idx + 1])
            except json.JSONDecodeError:
                pass

    preview = text[:400].replace("\n", "\\n")
    raise ValueError(f"Не удалось извлечь JSON. Ответ начинается с: {preview}")


def _fallback_report(variance_df: pd.DataFrame, chunks: list[Chunk]) -> ReportJSON:
    items: list[ReportItem] = []
    for _, row in variance_df.iterrows():
        rel = row.get("rel_variance")
        direction = "перерасход" if row["abs_variance"] > 0 else "экономия"
        rel_str = f"{rel:+.1%}" if rel is not None and pd.notna(rel) else "n/a"
        items.append(
            ReportItem(
                account=str(row["account"]),
                period=str(row["period"]),
                abs_variance=float(row["abs_variance"]),
                rel_variance=float(rel) if rel is not None and pd.notna(rel) else None,
                hypotheses=[
                    f"Отклонение {direction} относительно плана ({rel_str}).",
                    "Требуется уточнение причин у ответственного.",
                ],
                references=[],
                questions=[
                    f"Почему по статье «{row['account']}» отклонение {row['abs_variance']:+,.0f}?",
                    "Согласован ли перерасход/экономия с финансовым блоком?",
                ],
            )
        )

    total_abs = float(variance_df["abs_variance"].sum())
    summary = (
        f"По {len(items)} статьям зафиксированы отклонения. "
        f"Суммарное отклонение: {total_abs:+,.0f}. "
        "Отчёт сформирован в резервном режиме (LLM недоступна)."
    )

    return ReportJSON(
        summary=summary,
        items=items,
        meta=ReportMeta(
            model="fallback",
            generated_at=datetime.now(timezone.utc).isoformat(),
            masked=False,
        ),
    )


def _restore_numeric_fields(
    data: dict[str, Any], masker: Masker, variance_df: pd.DataFrame
) -> dict[str, Any]:
    """Заменяет токены маскирования и относит числовые поля к реальным значениям.

    YandexGPT иногда возвращает abs_variance как '__NUM_0010__' — в этом случае
    берём настоящее значение из variance_df по (account, period).
    """
    items = data.get("items", []) or []
    df_index = {}
    for _, row in variance_df.iterrows():
        key = (str(row["account"]).strip().lower(), str(row["period"]).strip())
        df_index[key] = row

    for item in items:
        acc = str(item.get("account", "")).strip().lower()
        per = str(item.get("period", "")).strip()
        row = df_index.get((acc, per))

        # abs_variance
        av = item.get("abs_variance")
        if av is None or (isinstance(av, str) and re.fullmatch(r"__NUM_\d+__", av.strip())):
            if row is not None:
                item["abs_variance"] = float(row["abs_variance"])

        # rel_variance
        rv = item.get("rel_variance")
        if rv is None or (isinstance(rv, str) and re.fullmatch(r"__NUM_\d+__%?", rv.strip())):
            if row is not None and pd.notna(row.get("rel_variance")):
                item["rel_variance"] = float(row["rel_variance"])

    return data


def generate(
    variance_df: pd.DataFrame,
    chunks: list[Chunk] | None = None,
    *,
    client: LLMClient | None = None,
    mask: bool = False,
    max_items: int = 10,
) -> ReportJSON:
    chunks = chunks or []
    df = variance_df.head(max_items).copy()

    client = client or LLMClient()

    if not client.available():
        print(f"[llm_agent] LLM not available: provider={client.config.provider}")
        return _fallback_report(df, chunks)

    # ВАЖНО: маскирование отключено для числовых полей. Мы не маскируем промпт
    # целиком, потому что YandexGPT повторяет токены в JSON, что ломает Pydantic.
    # Маскирование сумм — отдельный слой, см. src/mask.py.
    user_prompt = _build_user_prompt(df, chunks)
    masker = Masker() if mask else None
    if masker is not None:
        masked = masker.mask(user_prompt)
        user_prompt_masked = masked.text
    else:
        user_prompt_masked = user_prompt

    try:
        raw = client.complete(SYSTEM_PROMPT, user_prompt_masked)
        data = _extract_json(raw)

        # Восстановить числовые поля из исходного DataFrame
        data = _restore_numeric_fields(data, masker or Masker(), df)

        data.setdefault("items", [])
        data["meta"] = {
            "model": client.config.model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "masked": mask,
        }
        report = ReportJSON.model_validate(data)

        # Демаскировать текстовые поля (гипотезы, вопросы, summary, quotes)
        if masker is not None:
            report.summary = masker.unmask(report.summary)
            for item in report.items:
                item.account = masker.unmask(item.account)
                item.hypotheses = [masker.unmask(h) for h in item.hypotheses]
                item.questions = [masker.unmask(q) for q in item.questions]
                for ref in item.references:
                    ref.quote = masker.unmask(ref.quote)

        return report
    except Exception as e:
        print(f"[llm_agent] LLM call failed ({type(e).__name__}): {e}")
        import traceback

        traceback.print_exc()
        return _fallback_report(df, chunks)


def report_to_markdown(report: ReportJSON) -> str:
    lines: list[str] = [
        "# Аналитическая записка по отклонениям план/факт",
        "",
        f"*Сгенерировано: {report.meta.generated_at}*  ",
        f"*Модель: {report.meta.model}*  ",
    ]
    if report.meta.masked:
        lines.append("*Данные маскированы перед отправкой в LLM*")
    lines.extend(["", "## Резюме", "", report.summary, ""])

    for i, item in enumerate(report.items, 1):
        if item.rel_variance is not None:
            rel = f"{item.rel_variance:+.2%}"
        else:
            rel = "n/a"
        av = f"{item.abs_variance:+,.0f}" if item.abs_variance is not None else "n/a"
        lines.append(f"## {i}. {item.account} ({item.period})")
        lines.append("")
        lines.append(f"**Отклонение:** {av} ({rel})")
        lines.append("")
        if item.hypotheses:
            lines.append("**Гипотезы причин:**")
            lines.extend(f"- {h}" for h in item.hypotheses)
            lines.append("")
        if item.references:
            lines.append("**Ссылки на документы:**")
            for r in item.references:
                clause = f", п. {r.clause}" if r.clause else ""
                page = f", стр. {r.page}" if r.page else ""
                lines.append(f"- {r.source}{clause}{page}: «{r.quote}»")
            lines.append("")
        if item.questions:
            lines.append("**Вопросы ответственным:**")
            lines.extend(f"- {q}" for q in item.questions)
            lines.append("")

    return "\n".join(lines)


def report_to_dict(report: ReportJSON) -> dict[str, Any]:
    return report.model_dump()