from app.stt.base import BaseSTTEngine
from tempfile import NamedTemporaryFile
from pathlib import Path
from app.utils.audio_utils import save_bytes_as_wav


class KotibSTT(BaseSTTEngine):
    def __init__(self, model_name: str = "Kotib/uzbek_stt_v1"):
        self.model_name = model_name
        self.model = None

    def _load_model(self):
        if self.model is None:
            try:
                from whisper_jax import FlaxWhisperPipline
            except ImportError as exc:
                raise RuntimeError("Install whisper-jax to use KotibSTT") from exc
            self.model = FlaxWhisperPipline.from_pretrained(self.model_name)

    def transcribe_file(self, audio_path: str, language: str = "uz") -> str:
        self._load_model()
        try:
            result = self.model.transcribe(audio_path)
            return result["text"]
        except Exception as exc:
            raise RuntimeError(f"Kotib STT transcription failed: {exc}") from exc

    def transcribe_microphone_chunk(self, audio_bytes: bytes, language: str = "uz") -> str:
        self._load_model()
        with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            save_bytes_as_wav(audio_bytes, tmp_path)
        try:
            result = self.model.transcribe(tmp_path)
            return result["text"]
        finally:
            Path(tmp_path).unlink(missing_ok=True)
