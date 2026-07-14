from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import ROOT, settings
from app.errors import LocalAIError


class LocalTTSEngine:
    def __init__(self) -> None:
        self._model: Any | None = None
        self.output_dir = ROOT / "output"
        self.output_dir.mkdir(exist_ok=True)

    @property
    def model_path(self) -> Path:
        fine_tuned = settings.path(settings.tts_model_path)
        return fine_tuned if fine_tuned.is_dir() and any(path.name != ".gitkeep" for path in fine_tuned.rglob("*")) else settings.path(settings.tts_base_model_path)

    def load_model(self) -> dict[str, object]:
        if self._model is not None:
            return self.get_model_info()
        if not self.model_path.is_dir() or not any(path.name != ".gitkeep" for path in self.model_path.rglob("*")):
            raise LocalAIError("TTS_MODEL_NOT_FOUND", "Mahalliy TTS modeli topilmadi.", str(self.model_path))
        try:
            # Qwen's local package reads a directory checkpoint and does not contact a hosted API.
            from qwen_tts import Qwen3TTSModel
            self._model = Qwen3TTSModel.from_pretrained(str(self.model_path), local_files_only=True)
        except ImportError as exc:
            raise LocalAIError("TTS_DEPENDENCY_MISSING", "TTS uchun qwen-tts bog‘liqligi o‘rnatilmagan.", str(exc), True) from exc
        except Exception as exc:
            raise LocalAIError("TTS_LOAD_FAILED", "Mahalliy TTS modeli yuklanmadi.", str(exc), True) from exc
        return self.get_model_info()

    def unload_model(self) -> None:
        self._model = None

    def _reference_audio(self, speaker_id: str) -> Path:
        # The Base checkpoint has no built-in speaker. Preserve the API's
        # historical "default" value by selecting the local assistant profile.
        selected_speaker = "female_assistant" if speaker_id == "default" else speaker_id
        speaker_config = ROOT / "data" / "speakers" / selected_speaker / "speaker.json"
        if not speaker_config.is_file():
            raise LocalAIError("TTS_SPEAKER_NOT_FOUND", "Tanlangan TTS speaker topilmadi.", str(speaker_config))
        reference_name = json.loads(speaker_config.read_text(encoding="utf-8")).get("reference_audio")
        reference = speaker_config.parent / str(reference_name)
        if not reference.is_file():
            raise LocalAIError(
                "TTS_REFERENCE_AUDIO_NOT_FOUND",
                "Base TTS modeli uchun ruxsatli reference audio topilmadi.",
                f"{reference}. 3–10 soniyalik WAV audio qo‘shing yoki fine-tuned checkpoint o‘rnating.",
            )
        return reference

    def synthesize(self, text: str, speaker_id: str = "default", language: str = "uz", speed: float = 1.0, emotion: str = "neutral") -> dict[str, object]:
        started = time.perf_counter()
        fine_tuned_path = settings.path(settings.tts_model_path)
        # Do this before allocating the multi-GB Base checkpoint. A missing
        # reference recording is a configuration issue, not a reason to stall
        # the health endpoint while a model loads.
        reference_audio = (
            self._reference_audio(speaker_id)
            if self.model_path != fine_tuned_path
            else None
        )
        model = self._model or self.load_model() and self._model
        destination = self.output_dir / f"tts-{uuid.uuid4().hex}.wav"
        try:
            import soundfile as sf
            if self.model_path == fine_tuned_path:
                # A project fine-tune can expose custom speakers.
                wavs, sample_rate = model.generate_custom_voice(text=text, language=language, speaker=speaker_id, speed=speed)
            else:
                # Qwen Base is a local voice-cloning model. It has no default speaker and
                # needs the user's authorised reference audio.
                wavs, sample_rate = model.generate_voice_clone(
                    text=text,
                    language="Auto",
                    ref_audio=str(reference_audio),
                    x_vector_only_mode=True,
                )
            sf.write(str(destination), wavs[0], sample_rate)
        except LocalAIError:
            destination.unlink(missing_ok=True)
            raise
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise LocalAIError("TTS_GENERATION_FAILED", "Mahalliy TTS audiosi yaratilmagan.", str(exc), True) from exc
        duration_ms = round(sf.info(str(destination)).duration * 1000)
        return {"audioUrl": f"/audio/{destination.name}", "durationMs": duration_ms, "generationMs": round((time.perf_counter() - started) * 1000), "sampleRate": sample_rate, "model": str(self.model_path)}

    def clone_authorized_voice(self, *_: object, **__: object) -> None:
        raise LocalAIError("VOICE_CLONING_NOT_CONFIGURED", "Ovoz klonlash uchun ruxsatli namuna va mos checkpoint kerak.")

    def health_check(self) -> dict[str, object]:
        return {"loaded": self._model is not None, "modelExists": self.model_path.is_dir() and any(path.name != ".gitkeep" for path in self.model_path.rglob("*"))}

    def get_model_info(self) -> dict[str, object]:
        return {"loaded": self._model is not None, "path": str(self.model_path), "model": "Qwen3-TTS-12Hz-0.6B-Base"}


tts_engine = LocalTTSEngine()
