"""Маскирование сумм перед отправкой в LLM.

Маскируем ТОЛЬКО похожее на финансовые суммы:
- есть разделители тысяч (пробел, запятая), ИЛИ
- длина >= 6 знаков (миллион+), ИЛИ
- есть десятичная часть И длина >= 5.

Не маскируем: номера пунктов (4.2), годы (2024), короткие числа (45).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_NUMBER_RE = re.compile(r"-?\d[\d\s\u00a0,]*\.?\d*")


@dataclass
class MaskResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)


def _normalize_num(raw: str) -> str:
    return raw.replace(" ", "").replace("\u00a0", "").replace(",", "")


def _should_mask(raw: str) -> bool:
    """Решает, является ли число финансовой суммой."""
    has_thousand_sep = bool(re.search(r"[\s\u00a0,]", raw))
    normalized = _normalize_num(raw)
    has_decimal = "." in raw
    length = len(normalized)

    if has_thousand_sep:
        return True
    if has_decimal and length >= 5:
        return True
    if not has_decimal and length >= 6:
        return True
    return False


class Masker:
    """Маскирует суммы в тексте стабильными токенами."""

    def __init__(self, token_prefix: str = "__NUM_") -> None:
        self._prefix = token_prefix
        self._mapping: dict[str, str] = {}
        self._reverse: dict[str, str] = {}

    def _token_for(self, original: str) -> str:
        if original in self._reverse:
            return self._reverse[original]
        idx = len(self._reverse) + 1
        token = f"{self._prefix}{idx:04d}__"
        self._reverse[original] = token
        self._mapping[token] = original
        return token

    def mask(self, text: str) -> MaskResult:
        def _replace(m: re.Match[str]) -> str:
            raw = m.group(0)
            if not _should_mask(raw):
                return raw
            return self._token_for(_normalize_num(raw))

        masked = _NUMBER_RE.sub(_replace, text)
        return MaskResult(text=masked, mapping=dict(self._mapping))

    def unmask(self, text: str) -> str:
        out = text
        for token, original in self._mapping.items():
            out = out.replace(token, original)
        return out

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._mapping)