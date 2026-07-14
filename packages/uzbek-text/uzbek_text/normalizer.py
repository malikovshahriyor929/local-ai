from __future__ import annotations

import re

APOSTROPHE = "’"
_APOSTROPHES = re.compile(r"[ʻʼ‘`']")
_WHITESPACE = re.compile(r"\s+")


def normalize_display(text: str) -> str:
    """Keep UI text human-readable while normalising Uzbek apostrophes."""
    value = _APOSTROPHES.sub(APOSTROPHE, text.strip())
    # The letter may occur inside a word (for example, so‘m), not only at its start.
    value = re.sub(r"([oO])" + APOSTROPHE, r"\1‘", value)
    value = re.sub(r"([gG])" + APOSTROPHE, r"\1‘", value)
    return _WHITESPACE.sub(" ", value)


_ONES = ["nol", "bir", "ikki", "uch", "to‘rt", "besh", "olti", "yetti", "sakkiz", "to‘qqiz"]
_TENS = ["", "o‘n", "yigirma", "o‘ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to‘qson"]


def _number_to_uzbek(number: int) -> str:
    if number < 10:
        return _ONES[number]
    if number < 100:
        return " ".join(part for part in (_TENS[number // 10], _ONES[number % 10] if number % 10 else "") if part)
    if number < 1_000:
        return " ".join(part for part in (_ONES[number // 100], "yuz", _number_to_uzbek(number % 100) if number % 100 else "") if part)
    if number < 1_000_000:
        return " ".join(part for part in (_number_to_uzbek(number // 1_000), "ming", _number_to_uzbek(number % 1_000) if number % 1_000 else "") if part)
    return str(number)


def to_speech_text(text: str) -> str:
    """A deliberately conservative speech form; visible text is never changed."""
    display = normalize_display(text)
    display = re.sub(r"(\d+)\s*%", lambda m: f"{_number_to_uzbek(int(m.group(1)))} foiz", display)
    display = re.sub(r"(\d[\d\s]*)\s*so‘m", lambda m: f"{_number_to_uzbek(int(m.group(1).replace(' ', '')))} so‘m", display, flags=re.I)
    return re.sub(r"\b\d+\b", lambda m: _number_to_uzbek(int(m.group(0))) if int(m.group(0)) < 1_000_000 else m.group(0), display)
