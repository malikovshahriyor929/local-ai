"""Uzbek Latin -> Cyrillic transliteration for the MMS TTS voice.

The official Meta MMS Uzbek checkpoint (facebook/mms-tts-uzb-script_cyrillic)
only reads Cyrillic. User-facing text in this project is Latin Uzbek, so TTS
input is transliterated right before synthesis. Display text is never changed.
"""
from __future__ import annotations

_DIGRAPHS = [
    ("o'", "ў"), ("O'", "Ў"), ("g'", "ғ"), ("G'", "Ғ"),
    ("sh", "ш"), ("Sh", "Ш"), ("SH", "Ш"),
    ("ch", "ч"), ("Ch", "Ч"), ("CH", "Ч"),
    ("yo", "ё"), ("Yo", "Ё"), ("YO", "Ё"),
    ("yu", "ю"), ("Yu", "Ю"), ("YU", "Ю"),
    ("ya", "я"), ("Ya", "Я"), ("YA", "Я"),
    ("ye", "е"), ("Ye", "Е"), ("YE", "Е"),
    ("ts", "ц"), ("Ts", "Ц"), ("TS", "Ц"),
]

_SINGLES = {
    "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "x": "х", "y": "й", "z": "з", "'": "ъ",
    "A": "А", "B": "Б", "D": "Д", "E": "Е", "F": "Ф", "G": "Г", "H": "Ҳ",
    "I": "И", "J": "Ж", "K": "К", "L": "Л", "M": "М", "N": "Н", "O": "О",
    "P": "П", "Q": "Қ", "R": "Р", "S": "С", "T": "Т", "U": "У", "V": "В",
    "X": "Х", "Y": "Й", "Z": "З",
}


def latin_to_cyrillic(text: str) -> str:
    for apostrophe in ("ʻ", "ʼ", "‘", "’", "`"):
        text = text.replace(apostrophe, "'")
    for latin, cyrillic in _DIGRAPHS:
        text = text.replace(latin, cyrillic)
    out: list[str] = []
    prev_alpha = False
    for char in text:
        # Word-initial "e" is pronounced/written "э" in Cyrillic Uzbek.
        if char in ("e", "E") and not prev_alpha:
            out.append("Э" if char == "E" else "э")
        else:
            out.append(_SINGLES.get(char, char))
        prev_alpha = char.isalpha() or char == "'"
    return "".join(out)
