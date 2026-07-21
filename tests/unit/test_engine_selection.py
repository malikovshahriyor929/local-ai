from types import SimpleNamespace

from app.config import settings
from app.engines.stt import LocalSTTEngine
from app.engines.tts import LocalTTSEngine
from app.utils.translit import latin_to_cyrillic


def test_empty_hypothesis_yields_empty_string_not_object_repr() -> None:
    hypothesis = SimpleNamespace(text="", y_sequence=[])
    assert LocalSTTEngine._result_text(hypothesis) == ""
    assert LocalSTTEngine._result_text(SimpleNamespace(text=None)) == ""
    assert LocalSTTEngine._result_text(None) == ""


def test_translit_digraphs_apostrophes_and_word_initial_e() -> None:
    assert latin_to_cyrillic("o'zbek") == "ўзбек"
    assert latin_to_cyrillic("g'alaba yaxshi") == "ғалаба яхши"
    assert latin_to_cyrillic("sun'iy") == "сунъий"
    assert latin_to_cyrillic("Endi ekran") == "Энди экран"
    assert latin_to_cyrillic("Salom, ob-havo!") == "Салом, об-ҳаво!"
    # Typographic apostrophes normalise to the same output.
    assert latin_to_cyrillic("oʻzbek") == latin_to_cyrillic("o'zbek")


def test_stt_engine_mode_is_read_from_settings(monkeypatch) -> None:
    engine = LocalSTTEngine()
    monkeypatch.setattr(settings, "stt_engine", "whisper")
    assert engine.engine == "whisper"
    monkeypatch.setattr(settings, "stt_engine", "HYBRID")
    assert engine.engine == "hybrid"


def test_tts_engine_selection_rules(monkeypatch, tmp_path) -> None:
    engine = LocalTTSEngine()
    # Force "no fine-tuned checkpoint" regardless of local disk state.
    monkeypatch.setattr(settings, "tts_model_path", str(tmp_path / "missing-finetune"))

    monkeypatch.setattr(settings, "tts_engine", "mms")
    assert engine._uses_mms("user_voice") is True

    monkeypatch.setattr(settings, "tts_engine", "qwen3")
    assert engine._uses_mms("default") is False

    monkeypatch.setattr(settings, "tts_engine", "auto")
    assert engine._uses_mms("user_voice") is False  # explicit clone speaker

    monkeypatch.setattr(LocalTTSEngine, "_active_speaker", lambda self: None)
    assert engine._uses_mms("default") is True  # fresh setup speaks via MMS

    monkeypatch.setattr(LocalTTSEngine, "_active_speaker", lambda self: "user_voice")
    assert engine._uses_mms("default") is False  # activated clone wins
