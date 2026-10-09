from __future__ import annotations

from src.mask import Masker


def test_mask_basic() -> None:
    m = Masker()
    res = m.mask("Перерасход 1 350 000 рублей")
    assert "__NUM_0001__" in res.text
    assert res.mapping["__NUM_0001__"] == "1350000"


def test_mask_same_number_same_token() -> None:
    m = Masker()
    res = m.mask("план 1000000 и факт 1000000")
    tokens = [t for t in res.mapping if "NUM" in t]
    assert len(tokens) == 1


def test_mask_ignores_short_numbers() -> None:
    m = Masker()
    res = m.mask("пункт 4.2 договора 45/2024")
    assert len(res.mapping) == 0


def test_mask_unmask_roundtrip() -> None:
    m = Masker()
    original = "Перерасход 1 350 000 рублей против плана 1 000 000"
    res = m.mask(original)
    restored = m.unmask(res.text).replace(" ", "")
    assert "1350000" in restored
    assert "1000000" in restored


def test_mask_comma_separated() -> None:
    m = Masker()
    res = m.mask("выручка 1,000,000")
    assert "__NUM_0001__" in res.text
    assert res.mapping["__NUM_0001__"] == "1000000"