"""Настройка логирования с маскированием сумм и PII.

Соответствует Epic 8 (Security, финальный штрих).
Логи не должны содержать реальные финансовые цифры.
"""

from __future__ import annotations

import logging
import re
from typing import Any

# Простое правило: маскировать длинные числа (>=6 знаков) и email
_NUM_RE = re.compile(r"\b\d{6,}\b")
_EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")


def sanitize(text: str) -> str:
    """Заменяет длинные числа и email на токены."""
    text = _NUM_RE.sub("__NUM__", text)
    text = _EMAIL_RE.sub("__EMAIL__", text)
    return text


class SanitizingFormatter(logging.Formatter):
    """Форматтер, который маскирует сообщение перед выводом."""

    def format(self, record: logging.LogRecord) -> str:
        # Копируем, чтобы не портить оригинальный record
        original_msg = record.msg
        original_args = record.args
        try:
            record.msg = sanitize(str(record.msg))
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


def setup_logging(level: int = logging.INFO) -> None:
    """Инициализирует root-logger с маскирующим форматтером."""
    root = logging.getLogger()
    # Убираем старые хендлеры, чтобы не дублировать
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(
        SanitizingFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# Запрещённые ключи в extra — если кто-то попытается залогировать
FORBIDDEN_KEYS = frozenset({"plan", "fact", "amount", "sum", "variance", "abs_variance"})