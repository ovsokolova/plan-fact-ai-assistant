"""LLM-агент: генерация аналитической записки (ADR-0001, ADR-0004)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv(override=True)

from src.mask import Masker
from src.rag import Chunk


class Reference(BaseModel):
    source: str
    page: int | None = None
    clause: str | None = None
    quote: str = ""


class ReportItem(BaseModel):
    account: str
    period: str
    abs_variance: float
    rel_variance: float | None = None
    hypotheses: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


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
6. Ответ — СТРОГО валидный JSON без markdown-обёртки:
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
                model=os.getenv("YANDEX_MODEL", "yandexgpt-lite"),
                api_key=os.getenv("YANDEX_API_KEY"),
                base_url=os.getenv("YANDEX_FOLDER_ID"),
                timeout=int(os.getenv("YANDEX_TIMEOUT", "60")),
                temperature=float(os.getenv("YANDEX_TEMPERATURE", "0.2")),
            )

        return cls(
            provider=provider,
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OLLAMA_BASE_URL") if provider == "ollama" else None,
        )


class LLMClient:
    """Обёртка над OpenAI-совместимым API (OpenAI / Ollama)."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()

    def available(self) -> bool:
        p = self.config.provider
        if p == "ollama":
            return bool(self.config.base_url)
        if p == "yandex":
            # base_url хранит folder_id
            return bool(self.config.api_key and self.config.base_url)
        return bool(self.config.api_key)

    def complete(self, system: str, user: str) -> str:
        if not self.available():
            raise RuntimeError("LLM not configured")
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
        return _fallback_report(df, chunks)

    masker = Masker() if mask else None
    user_prompt = _build_user_prompt(df, chunks)
    if masker is not None:
        user_prompt = masker.mask(user_prompt).text

    try:
        raw = client.complete(SYSTEM_PROMPT, user_prompt)
        data = json.loads(raw)
        data.setdefault("items", [])
        data["meta"] = {
            "model": client.config.model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "masked": mask,
        }
        report = ReportJSON.model_validate(data)

        if masker is not None:
            for item in report.items:
                item.account = masker.unmask(item.account)
                item.hypotheses = [masker.unmask(h) for h in item.hypotheses]
                item.questions = [masker.unmask(q) for q in item.questions]
                for ref in item.references:
                    ref.quote = masker.unmask(ref.quote)
            report.summary = masker.unmask(report.summary)

        return report
    except Exception:  # noqa: BLE001
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
        rel = f"{item.rel_variance:+.2%}" if item.rel_variance is not None else "n/a"
        lines.append(f"## {i}. {item.account} ({item.period})")
        lines.append("")
        lines.append(f"**Отклонение:** {item.abs_variance:+,.0f} ({rel})")
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