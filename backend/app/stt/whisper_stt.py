import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from app.stt.base import BaseSTTEngine
from app.utils.audio_utils import save_bytes_as_wav


class FasterWhisperSTT(BaseSTTEngine):
    def __init__(self, model_name: str = "openai/whisper-small"):
        self.model_name = model_name
        self.model = None

    def _load_model(self):
        if self.model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError("Install faster-whisper to use FasterWhisperSTT") from exc
            self.model = WhisperModel(self.model_name, device="auto", compute_type="int8" if os.getenv("USE_INT8", "1") == "1" else "float16")

    def transcribe_file(self, audio_path: str, language: str = "uz") -> str:
        self._load_model()
        segments, _ = self.model.transcribe(audio_path, language=language, task="transcribe")
        return " ".join([segment.text for segment in segments])

    def transcribe_microphone_chunk(self, audio_bytes: bytes, language: str = "uz") -> str:
        self._load_model()
        with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            save_bytes_as_wav(audio_bytes, tmp_path)
        try:
            segments, _ = self.model.transcribe(tmp_path, language=language, task="transcribe")
            return " ".join([segment.text for segment in segments])
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class WhisperFallbackSTT(BaseSTTEngine):
    def __init__(self, model_name: str = "openai/whisper-small"):
        self.model_name = model_name
        self.model = None

    def _load_model(self):
        if self.model is None:
            try:
                import whisper
            except ImportError as exc:
                raise RuntimeError("Install openai-whisper to use WhisperFallbackSTT") from exc
            self.model = whisper.load_model(self.model_name)

    def transcribe_file(self, audio_path: str, language: str = "uz") -> str:
        self._load_model()
        result = self.model.transcribe(audio_path, language=language)
        return result.get("text", "")

    def transcribe_microphone_chunk(self, audio_bytes: bytes, language: str = "uz") -> str:
        self._load_model()
        with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            save_bytes_as_wav(audio_bytes, tmp_path)
        try:
            result = self.model.transcribe(tmp_path, language=language)
            return result.get("text", "")
        finally:
            Path(tmp_path).unlink(missing_ok=True)
