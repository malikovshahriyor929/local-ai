import re

NORMALIZE_MAP = {
    "o'": "o‘",
    "g'": "g‘",
    "oʻ": "o‘",
    "gʻ": "g‘",
    "O'": "O‘",
    "G'": "G‘",
    "Oʻ": "O‘",
    "Gʻ": "G‘",
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = text.strip()
    for key, value in NORMALIZE_MAP.items():
        normalized = normalized.replace(key, value)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*([,.!?;:])\s*", r"\1 ", normalized)
    normalized = re.sub(r"([?.!]){2,}", r"\1", normalized)
    normalized = normalized.strip()
    return normalized
