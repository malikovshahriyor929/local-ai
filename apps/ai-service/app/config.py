from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Uzbek Local Voice AI"
    offline_mode: bool = False
    ai_service_host: str = "127.0.0.1"
    ai_service_port: int = 8001
    llm_backend: str = "llama.cpp"
    llm_model_path: str = "./models/llm/model.gguf"
    llm_context_size: int = 8192
    llm_gpu_layers: int = -1
    llm_threads: int = 8
    llm_batch_size: int = 512
    llm_temperature: float = 0.4
    llm_top_p: float = 0.9
    llm_max_tokens: int = 700
    stt_engine: str = "hybrid"  # hybrid | fastconformer | whisper
    stt_model_path: str = "./models/stt/fastconformer"
    stt_whisper_model_path: str = "./models/stt/whisper-large-v3"
    stt_whisper_compute: str = "int8"
    stt_language: str = "uz"
    tts_engine: str = "auto"  # auto | mms | qwen3
    tts_model_path: str = "./models/tts/uzbek-voice"
    tts_base_model_path: str = "./models/tts/qwen3-tts-base"
    tts_mms_model_path: str = "./models/tts/mms-uzbek"
    tts_language: str = "uz"
    tts_default_speaker: str = "female_assistant"
    embedding_model_path: str = "./models/embeddings/model"
    max_recording_seconds: int = 120
    audio_retention_hours: int = 24
    auto_play_assistant_audio: bool = True
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    def path(self, value: str) -> Path:
        return (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value)


settings = Settings()
