from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages/uzbek-text"))
from uzbek_text import normalize_display, to_speech_text


def test_normalizes_apostrophes_without_replacing_visible_text_with_words():
    assert normalize_display("o'quvchi gʻalaba") == "o‘quvchi g‘alaba"
    assert to_speech_text("125 000 so‘m") == "bir yuz yigirma besh ming so‘m"


def test_percentage_is_spoken_but_display_form_remains_separate():
    assert normalize_display("20% chegirma") == "20% chegirma"
    assert to_speech_text("20% chegirma") == "yigirma foiz chegirma"
