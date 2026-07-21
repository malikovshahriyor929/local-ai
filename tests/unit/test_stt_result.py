from types import SimpleNamespace

from app.engines.stt import LocalSTTEngine


def test_nemo_hypothesis_renders_only_transcript_text() -> None:
    hypothesis = SimpleNamespace(text="O‘zbekcha gapir", y_sequence=[59, 984])

    assert LocalSTTEngine._result_text(hypothesis) == "O‘zbekcha gapir"


def test_stt_result_text_handles_plain_string_and_mapping() -> None:
    assert LocalSTTEngine._result_text(" Salom ") == "Salom"
    assert LocalSTTEngine._result_text({"text": " Assalomu alaykum "}) == "Assalomu alaykum"
