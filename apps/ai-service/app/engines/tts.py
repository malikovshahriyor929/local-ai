from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
import wave
from pathlib import Path
from typing import Any

from app.config import ROOT, settings
from app.errors import LocalAIError


class LocalTTSEngine:
    """Uzbek TTS with two local engines.

    - MMS (facebook/mms-tts-uzb-script_cyrillic): built-in Uzbek voice, fast
      CPU synthesis, no reference recording needed. Default for new setups.
    - Qwen3-TTS: zero-shot voice cloning / fine-tuned checkpoints. Used when a
      clone speaker is explicitly requested or activated.
    """

    def __init__(self) -> None:
        self._model: Any | None = None
        self._loaded_model_path: Path | None = None
        self._clone_prompts: dict[str, Any] = {}
        self._mms_model: Any | None = None
        self._mms_tokenizer: Any | None = None
        self.output_dir = ROOT / "output"
        self.output_dir.mkdir(exist_ok=True)

    @property
    def engine_mode(self) -> str:
        mode = settings.tts_engine.strip().lower()
        return mode if mode in {"auto", "mms", "qwen3"} else "auto"

    @property
    def mms_model_path(self) -> Path:
        return settings.path(settings.tts_mms_model_path)

    @property
    def model_path(self) -> Path:
        fine_tuned = settings.path(settings.tts_model_path)
        # A run metadata file is written before fine-tuning starts; it must not
        # make a partial/failed run look like a loadable checkpoint.
        return fine_tuned if (fine_tuned / "config.json").is_file() else settings.path(settings.tts_base_model_path)

    def _uses_mms(self, speaker_id: str) -> bool:
        mode = self.engine_mode
        if mode == "mms":
            return True
        if mode == "qwen3":
            return False
        if speaker_id not in ("default", "mms"):
            return False
        if self.model_path != settings.path(settings.tts_base_model_path):
            return False  # a fine-tuned checkpoint is the user's chosen voice
        if self._active_speaker():
            return False  # the user explicitly activated a cloned speaker
        return True

    def load_model(self, model_path: Path | None = None) -> dict[str, object]:
        selected_path = model_path or self.model_path
        if self._model is not None and self._loaded_model_path == selected_path:
            return self.get_model_info()
        if not selected_path.is_dir() or not any(path.name != ".gitkeep" for path in selected_path.rglob("*")):
            raise LocalAIError("TTS_MODEL_NOT_FOUND", "Mahalliy TTS modeli topilmadi.", str(selected_path))
        try:
            # Qwen's local package reads a directory checkpoint and does not contact a hosted API.
            from qwen_tts import Qwen3TTSModel
            self._model = Qwen3TTSModel.from_pretrained(str(selected_path), local_files_only=True)
            self._loaded_model_path = selected_path
            # Clone prompts contain tensors tied to the previous checkpoint.
            self._clone_prompts.clear()
        except ImportError as exc:
            raise LocalAIError("TTS_DEPENDENCY_MISSING", "TTS uchun qwen-tts bog‘liqligi o‘rnatilmagan.", str(exc), True) from exc
        except Exception as exc:
            raise LocalAIError("TTS_LOAD_FAILED", "Mahalliy TTS modeli yuklanmadi.", str(exc), True) from exc
        return self.get_model_info()

    def unload_model(self) -> None:
        self._model = None
        self._loaded_model_path = None
        self._clone_prompts.clear()
        self._mms_model = None
        self._mms_tokenizer = None

    def _load_mms(self) -> None:
        if self._mms_model is not None:
            return
        if not (self.mms_model_path / "config.json").is_file():
            raise LocalAIError("TTS_MODEL_NOT_FOUND", "MMS TTS modeli topilmadi.", str(self.mms_model_path))
        try:
            from transformers import AutoTokenizer, VitsModel
            self._mms_model = VitsModel.from_pretrained(str(self.mms_model_path), local_files_only=True)
            self._mms_tokenizer = AutoTokenizer.from_pretrained(str(self.mms_model_path), local_files_only=True)
        except ImportError as exc:
            raise LocalAIError("TTS_DEPENDENCY_MISSING", "TTS uchun transformers bog‘liqligi o‘rnatilmagan.", str(exc), True) from exc
        except Exception as exc:
            raise LocalAIError("TTS_LOAD_FAILED", "MMS TTS modeli yuklanmadi.", str(exc), True) from exc

    @staticmethod
    def _speech_text(text: str) -> str:
        """Expand numbers etc. into speakable Uzbek words when available."""
        try:
            try:
                from uzbek_text import to_speech_text
            except ImportError:
                import sys
                sys.path.insert(0, str(ROOT / "packages" / "uzbek-text"))
                from uzbek_text import to_speech_text
            return to_speech_text(text)
        except Exception:
            return text

    def _synthesize_mms(self, text: str, destination: Path, speed: float) -> tuple[Any, int]:
        from app.utils.translit import latin_to_cyrillic
        self._load_mms()
        import torch
        cyrillic = latin_to_cyrillic(self._speech_text(text))
        inputs = self._mms_tokenizer(cyrillic, return_tensors="pt")
        if inputs["input_ids"].shape[-1] == 0:
            raise LocalAIError("TTS_GENERATION_FAILED", "Matn MMS ovozi uchun bo‘sh yoki mos emas.", cyrillic)
        base_rate = float(getattr(self._mms_model.config, "speaking_rate", 1.0) or 1.0)
        self._mms_model.speaking_rate = base_rate * float(speed or 1.0)
        with torch.no_grad():
            waveform = self._mms_model(**inputs).waveform[0].numpy()
        return waveform, int(self._mms_model.config.sampling_rate)

    def _speaker_config(self, speaker_id: str) -> tuple[Path, dict[str, Any]]:
        speaker_config = ROOT / "data" / "speakers" / speaker_id / "speaker.json"
        if not speaker_config.is_file():
            raise LocalAIError("TTS_SPEAKER_NOT_FOUND", "Tanlangan TTS speaker topilmadi.", str(speaker_config))
        return speaker_config, json.loads(speaker_config.read_text(encoding="utf-8"))

    def _active_speaker(self) -> str | None:
        active = ROOT / "data" / "speakers" / "active.json"
        if not active.is_file():
            return None
        return json.loads(active.read_text(encoding="utf-8")).get("speaker_id")

    def _resolved_speaker(self, speaker_id: str) -> str:
        if speaker_id != "default":
            return speaker_id
        active_speaker = self._active_speaker()
        if active_speaker:
            return active_speaker
        if (ROOT / "data" / "speakers" / "user_voice" / "reference.wav").is_file():
            return "user_voice"
        return "female_assistant"

    def set_active_speaker(self, speaker_id: str) -> None:
        self._speaker_config(speaker_id)
        active = ROOT / "data" / "speakers" / "active.json"
        active.write_text(json.dumps({"speaker_id": speaker_id}, ensure_ascii=False), encoding="utf-8")

    def _reference_audio(self, speaker_id: str) -> Path:
        # The Base checkpoint has no built-in speaker. Prefer the user's
        # explicitly consented recording for the default conversation voice.
        user_reference = ROOT / "data" / "speakers" / "user_voice" / "reference.wav"
        selected_speaker = self._resolved_speaker(speaker_id)
        speaker_config, profile = self._speaker_config(selected_speaker)
        reference_name = profile.get("reference_audio")
        reference = speaker_config.parent / str(reference_name)
        if not reference.is_file():
            raise LocalAIError(
                "TTS_REFERENCE_AUDIO_NOT_FOUND",
                "Base TTS modeli uchun ruxsatli reference audio topilmadi.",
                f"{reference}. 3–15 soniyalik WAV audio qo‘shing yoki fine-tuned checkpoint o‘rnating.",
            )
        return reference

    def _reference_text(self, speaker_id: str) -> str | None:
        selected = self._resolved_speaker(speaker_id)
        _, profile = self._speaker_config(selected)
        return profile.get("reference_transcript")

    def _speaker_model_path(self, speaker_id: str) -> Path:
        """Return a speaker-specific fine-tuned checkpoint, when activated."""
        selected = self._resolved_speaker(speaker_id)
        try:
            _, profile = self._speaker_config(selected)
        except LocalAIError:
            return self.model_path
        configured = profile.get("model_path")
        if not configured:
            return self.model_path
        candidate = Path(str(configured))
        candidate = candidate if candidate.is_absolute() else ROOT / candidate
        try:
            candidate.resolve().relative_to((ROOT / "models" / "tts").resolve())
        except ValueError:
            return self.model_path
        return candidate if (candidate / "config.json").is_file() else self.model_path

    def save_authorized_reference(self, source: Path, speaker_id: str = "user_voice", transcript: str | None = None) -> dict[str, object]:
        """Store a user-consented voice sample in the local project only."""
        if not shutil.which("ffmpeg"):
            raise LocalAIError("AUDIO_CONVERSION_FAILED", "Ovoz namunasini tayyorlash uchun FFmpeg topilmadi.")
        speaker_dir = ROOT / "data" / "speakers" / speaker_id
        speaker_dir.mkdir(parents=True, exist_ok=True)
        destination = speaker_dir / "reference.wav"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(destination)],
                check=True,
                capture_output=True,
                text=True,
            )
            with wave.open(str(destination), "rb") as wav:
                duration = wav.getnframes() / wav.getframerate()
        except (subprocess.CalledProcessError, wave.Error) as exc:
            destination.unlink(missing_ok=True)
            details = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            raise LocalAIError("VOICE_REFERENCE_INVALID", "Ovoz namunasi o‘qilmadi.", details) from exc
        if not 3 <= duration <= 15:
            destination.unlink(missing_ok=True)
            raise LocalAIError(
                "VOICE_REFERENCE_DURATION_INVALID",
                "Ovoz namunasi 3–15 soniya bo‘lishi kerak.",
                f"Qabul qilingan davomiylik: {duration:.1f} soniya.",
            )
        (speaker_dir / "speaker.json").write_text(
            json.dumps(
                {
                    "speaker_id": speaker_id,
                    "display_name": "Mening ovozim" if speaker_id == "user_voice" else speaker_id.title(),
                    "type": "consented_voice_clone_reference",
                    "language": settings.tts_language,
                    "reference_audio": "reference.wav",
                    "reference_transcript": transcript or "",
                    "permission": "owned_by_user",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self._clone_prompts = {key: value for key, value in self._clone_prompts.items() if not key.startswith(f"{speaker_id}:")}
        return {"speakerId": speaker_id, "durationSeconds": round(duration, 1)}

    def _synthesize_qwen3(self, text: str, speaker_id: str, language: str, speed: float) -> tuple[Any, int]:
        selected_path = self._speaker_model_path(speaker_id)
        base_path = settings.path(settings.tts_base_model_path)
        # Do this before allocating the multi-GB Base checkpoint. A missing
        # reference recording is a configuration issue, not a reason to stall
        # the health endpoint while a model loads.
        reference_audio = (
            self._reference_audio(speaker_id)
            if selected_path == base_path
            else None
        )
        self.load_model(selected_path)
        model = self._model
        if selected_path != base_path:
            # A project fine-tune can expose custom speakers.
            wavs, sample_rate = model.generate_custom_voice(text=text, language=language, speaker=self._resolved_speaker(speaker_id), speed=speed)
        else:
            # Qwen Base is a local voice-cloning model. It has no default speaker and
            # needs the user's authorised reference audio.
            reference_text = self._reference_text(speaker_id)
            cache_key = f"{speaker_id}:{reference_audio.stat().st_mtime_ns}:{reference_text or ''}"
            prompt = self._clone_prompts.get(cache_key)
            if prompt is None:
                prompt = model.create_voice_clone_prompt(
                    ref_audio=str(reference_audio),
                    ref_text=reference_text,
                    x_vector_only_mode=not bool(reference_text),
                )
                self._clone_prompts = {cache_key: prompt}
            wavs, sample_rate = model.generate_voice_clone(
                text=text,
                language="auto",
                voice_clone_prompt=prompt,
            )
        return wavs[0], int(sample_rate)

    def synthesize(self, text: str, speaker_id: str = "default", language: str = "uz", speed: float = 1.0, emotion: str = "neutral") -> dict[str, object]:
        started = time.perf_counter()
        destination = self.output_dir / f"tts-{uuid.uuid4().hex}.wav"
        engine_used = "mms" if self._uses_mms(speaker_id) else "qwen3"
        try:
            import soundfile as sf
            if engine_used == "mms":
                waveform, sample_rate = self._synthesize_mms(text, destination, speed)
            else:
                try:
                    waveform, sample_rate = self._synthesize_qwen3(text, speaker_id, language, speed)
                except LocalAIError as exc:
                    # In auto mode a missing clone reference must not block
                    # speech; the built-in MMS voice answers instead.
                    if self.engine_mode == "auto" and exc.code in {"TTS_REFERENCE_AUDIO_NOT_FOUND", "TTS_SPEAKER_NOT_FOUND"}:
                        engine_used = "mms"
                        waveform, sample_rate = self._synthesize_mms(text, destination, speed)
                    else:
                        raise
            sf.write(str(destination), waveform, sample_rate)
        except LocalAIError:
            destination.unlink(missing_ok=True)
            raise
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise LocalAIError("TTS_GENERATION_FAILED", "Mahalliy TTS audiosi yaratilmagan.", str(exc), True) from exc
        duration_ms = round(sf.info(str(destination)).duration * 1000)
        model_label = "facebook/mms-tts-uzb-script_cyrillic" if engine_used == "mms" else str(self._loaded_model_path or self._speaker_model_path(speaker_id))
        # The browser only talks to Next.js. Route playback through its local
        # proxy instead of exposing the internal AI-service port to the page.
        return {"audioUrl": f"/api/audio/play/{destination.name}", "durationMs": duration_ms, "generationMs": round((time.perf_counter() - started) * 1000), "sampleRate": sample_rate, "engine": engine_used, "model": model_label}

    def clone_authorized_voice(self, *_: object, **__: object) -> None:
        raise LocalAIError("VOICE_CLONING_NOT_CONFIGURED", "Ovoz klonlash uchun ruxsatli namuna va mos checkpoint kerak.")

    def health_check(self) -> dict[str, object]:
        default_uses_mms = self._uses_mms("default")
        uses_base_model = self._speaker_model_path("default") == settings.path(settings.tts_base_model_path)
        try:
            reference_exists = self._reference_audio("default").is_file()
        except LocalAIError:
            reference_exists = False
        mms_exists = (self.mms_model_path / "config.json").is_file()
        return {
            "loaded": self._model is not None or self._mms_model is not None,
            "engine": "mms" if default_uses_mms else "qwen3",
            "engineMode": self.engine_mode,
            "modelExists": mms_exists if default_uses_mms else (self._speaker_model_path("default").is_dir() and any(path.name != ".gitkeep" for path in self._speaker_model_path("default").rglob("*"))),
            "mmsModelExists": mms_exists,
            "referenceAudioRequired": uses_base_model and not default_uses_mms,
            "referenceAudioExists": reference_exists,
        }

    def get_model_info(self) -> dict[str, object]:
        default_uses_mms = self._uses_mms("default")
        return {
            "loaded": self._model is not None or self._mms_model is not None,
            "engine": "mms" if default_uses_mms else "qwen3",
            "engineMode": self.engine_mode,
            "path": str(self.mms_model_path if default_uses_mms else (self._loaded_model_path or self._speaker_model_path("default"))),
            "model": "facebook/mms-tts-uzb-script_cyrillic" if default_uses_mms else "Qwen3-TTS-12Hz-0.6B-Base",
        }


tts_engine = LocalTTSEngine()
