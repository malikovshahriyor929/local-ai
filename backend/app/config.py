from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    stt_engine: str = "faster-whisper"
    stt_language: str = "uz"
    tts_engine: str = "matcha"
    # Compatibility adapter for the project-owned FastAPI service, never Ollama.
    llm_base_url: str = "http://127.0.0.1:8001"
    llm_model: str = "models/llm/model.gguf"
    default_speaker: str = "female_assistant"
    audio_output_dir: str = "../data/audio_output"
    speakers_dir: str = "../data/speakers"
    processed_audio_dir: str = "../data/processed_audio"
    system_prompt: str = "Siz tabiiy va hurmatli o‘zbek tilida javob beradigan lokal yordamchisiz. Foydalanuvchi bilan samimiy va aniq muloqot qiling."

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
