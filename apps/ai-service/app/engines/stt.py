from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.errors import LocalAIError


class LocalSTTEngine:
    def __init__(self) -> None:
        self._model: Any | None = None

    @property
    def model_path(self) -> Path:
        return settings.path(settings.stt_model_path)

    @property
    def checkpoint_path(self) -> Path | None:
        """The Uzbek model ships as `uzbek_fast_conformer_hybrid_v3.nemo`, not `model.nemo`."""
        preferred = self.model_path / "model.nemo"
        if preferred.is_file():
            return preferred
        return next(iter(self.model_path.glob("*.nemo")), None)

    def load_model(self) -> dict[str, object]:
        if self._model is not None:
            return self.get_model_info()
        checkpoint = self.checkpoint_path
        if checkpoint is None:
            raise LocalAIError("STT_MODEL_NOT_FOUND", "Mahalliy STT modeli topilmadi.", str(self.model_path))
        try:
            from nemo.collections.asr.models import ASRModel
            self._model = ASRModel.restore_from(str(checkpoint), map_location="cpu")
        except ImportError as exc:
            raise LocalAIError("STT_DEPENDENCY_MISSING", "STT uchun NeMo bog‘liqligi o‘rnatilmagan.", str(exc), True) from exc
        except Exception as exc:
            raise LocalAIError("STT_LOAD_FAILED", "Mahalliy STT modeli yuklanmadi.", str(exc), True) from exc
        return self.get_model_info()

    def unload_model(self) -> None:
        self._model = None

    def _convert_to_wav(self, source: Path) -> Path:
        if source.suffix.lower() == ".wav":
            return source
        if not shutil.which("ffmpeg"):
            raise LocalAIError("AUDIO_CONVERSION_FAILED", "Audio formatini o‘girish uchun FFmpeg topilmadi.")
        destination = Path(tempfile.mkstemp(suffix=".wav")[1])
        try:
            subprocess.run(["ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "16000", str(destination)], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            destination.unlink(missing_ok=True)
            raise LocalAIError("AUDIO_CONVERSION_FAILED", "Audio formatini o‘girishda xatolik yuz berdi.", exc.stderr) from exc
        return destination

    def transcribe(self, source: Path) -> dict[str, object]:
        started = time.perf_counter()
        model = self._model or self.load_model() and self._model
        wav = self._convert_to_wav(source)
        try:
            result = model.transcribe([str(wav)], batch_size=1)
            text = str(result[0]).strip() if result else ""
        finally:
            if wav != source:
                wav.unlink(missing_ok=True)
        if not text:
            raise LocalAIError("EMPTY_TRANSCRIPTION", "Nutq aniqlanmadi. Qayta urinib ko‘ring.")
        return {"text": text, "normalizedText": text, "language": settings.stt_language, "model": str(self.model_path), "durationMs": round((time.perf_counter() - started) * 1000), "confidence": None}

    def transcribe_stream(self, source: Path):
        yield self.transcribe(source)

    def health_check(self) -> dict[str, object]:
        return {"loaded": self._model is not None, "modelExists": self.checkpoint_path is not None}

    def get_model_info(self) -> dict[str, object]:
        return {"loaded": self._model is not None, "path": str(self.model_path), "model": "uzinfocom-edu-ai/asr-uz-fastconformer-large"}


stt_engine = LocalSTTEngine()
