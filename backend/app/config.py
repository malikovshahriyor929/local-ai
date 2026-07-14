from pydantic import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    stt_engine: str = "faster-whisper"
    stt_language: str = "uz"
    tts_engine: str = "matcha"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "gpt-4o-mini"  # default local-like model name
    default_speaker: str = "female_assistant"
    audio_output_dir: str = "../data/audio_output"
    speakers_dir: str = "../data/speakers"
    processed_audio_dir: str = "../data/processed_audio"
    system_prompt: str = "Siz tabiiy va hurmatli o‘zbek tilida javob beradigan lokal yordamchisiz. Foydalanuvchi bilan samimiy va aniq muloqot qiling."

    class Config:
        env_file = ".env"

settings = Settings()
