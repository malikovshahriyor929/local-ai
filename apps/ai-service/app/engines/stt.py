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
    """Uzbek STT with two local backends.

    - FastConformer (Uzbek-specialised) is accurate on clean speech but can
      return an empty hypothesis on some real recordings.
    - faster-whisper large-v3 always yields text but is weaker at Uzbek.

    The default "hybrid" mode runs FastConformer first and falls back to
    Whisper only when FastConformer produces nothing.
    """

    def __init__(self) -> None:
        self._model: Any | None = None
        self._whisper: Any | None = None

    @property
    def engine(self) -> str:
        return settings.stt_engine.strip().lower()

    @property
    def model_path(self) -> Path:
        return settings.path(settings.stt_model_path)

    @property
    def whisper_model_path(self) -> Path:
        return settings.path(settings.stt_whisper_model_path)

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
        self._whisper = None

    def _load_whisper(self) -> Any:
        if self._whisper is not None:
            return self._whisper
        if not (self.whisper_model_path / "model.bin").is_file():
            raise LocalAIError("STT_MODEL_NOT_FOUND", "Whisper STT modeli topilmadi.", str(self.whisper_model_path))
        try:
            from faster_whisper import WhisperModel
            self._whisper = WhisperModel(str(self.whisper_model_path), device="cpu", compute_type=settings.stt_whisper_compute)
        except ImportError as exc:
            raise LocalAIError("STT_DEPENDENCY_MISSING", "STT uchun faster-whisper bog‘liqligi o‘rnatilmagan.", str(exc), True) from exc
        except Exception as exc:
            raise LocalAIError("STT_LOAD_FAILED", "Whisper STT modeli yuklanmadi.", str(exc), True) from exc
        return self._whisper

    def _transcribe_whisper(self, wav: Path) -> str:
        model = self._load_whisper()
        try:
            segments, _ = model.transcribe(
                str(wav),
                language=settings.stt_language,
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:
            raise LocalAIError("STT_TRANSCRIBE_FAILED", "Whisper transkripsiyasi bajarilmadi.", str(exc), True) from exc

    def _transcribe_fastconformer(self, wav: Path) -> str:
        if self._model is None:
            self.load_model()
        try:
            result = self._model.transcribe([str(wav)], batch_size=1, verbose=False)
        except TypeError:
            result = self._model.transcribe([str(wav)], batch_size=1)
        # NeMo may return a string or a Hypothesis object. Serialising the
        # latter leaks decoder internals such as `y_sequence` into the chat.
        return self._result_text(result[0] if result else None)

    def _convert_to_wav(self, source: Path) -> Path:
        # Always normalise, including .wav inputs: the model expects 16 kHz mono
        # PCM, while browser recordings and TTS outputs arrive at 24-48 kHz.
        if not shutil.which("ffmpeg"):
            raise LocalAIError("AUDIO_CONVERSION_FAILED", "Audio formatini o‘girish uchun FFmpeg topilmadi.")
        destination = Path(tempfile.mkstemp(suffix=".wav")[1])
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destination)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            destination.unlink(missing_ok=True)
            raise LocalAIError("AUDIO_CONVERSION_FAILED", "Audio formatini o‘girishda xatolik yuz berdi.", exc.stderr) from exc
        return destination

    @staticmethod
    def _result_text(result: object | None) -> str:
        """Extract only the transcript text from NeMo's variable return types.

        A Hypothesis with empty `text` must yield "", never str(result):
        serialising the object leaks decoder internals into the chat.
        """
        if result is None:
            return ""
        if isinstance(result, str):
            return result.strip()
        if hasattr(result, "text"):
            return str(getattr(result, "text") or "").strip()
        if isinstance(result, dict):
            return str(result.get("text") or "").strip()
        return str(result).strip()

    def transcribe(self, source: Path) -> dict[str, object]:
        started = time.perf_counter()
        engine = self.engine if self.engine in {"hybrid", "fastconformer", "whisper"} else "hybrid"
        wav = self._convert_to_wav(source)
        text = ""
        used = ""
        try:
            if engine in {"hybrid", "fastconformer"}:
                try:
                    text = self._transcribe_fastconformer(wav)
                    used = "fastconformer"
                except LocalAIError:
                    if engine == "fastconformer":
                        raise
                    text = ""
            if not text and engine in {"hybrid", "whisper"}:
                text = self._transcribe_whisper(wav)
                used = "whisper"
        finally:
            if wav != source:
                wav.unlink(missing_ok=True)
        if not text:
            raise LocalAIError("EMPTY_TRANSCRIPTION", "Nutq aniqlanmadi. Qayta urinib ko‘ring.")
        model_used = str(self.whisper_model_path) if used == "whisper" else str(self.model_path)
        return {"text": text, "normalizedText": text, "language": settings.stt_language, "model": model_used, "engine": used, "durationMs": round((time.perf_counter() - started) * 1000), "confidence": None}

    def transcribe_stream(self, source: Path):
        yield self.transcribe(source)

    def health_check(self) -> dict[str, object]:
        return {
            "loaded": self._model is not None or self._whisper is not None,
            "engine": self.engine,
            "modelExists": self.checkpoint_path is not None,
            "whisperModelExists": (self.whisper_model_path / "model.bin").is_file(),
        }

    def get_model_info(self) -> dict[str, object]:
        return {
            "loaded": self._model is not None or self._whisper is not None,
            "engine": self.engine,
            "path": str(self.model_path),
            "whisperPath": str(self.whisper_model_path),
            "model": "uzinfocom-edu-ai/asr-uz-fastconformer-large + faster-whisper-large-v3 fallback",
        }


stt_engine = LocalSTTEngine()
