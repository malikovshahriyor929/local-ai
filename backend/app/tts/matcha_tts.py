import os
from pathlib import Path
from typing import List
from app.tts.base import BaseTTSEngine
from app.speakers.manager import SpeakerManager
from app.config import settings
from app.utils.audio_utils import save_wav_bytes

class MatchaUzbekTTS(BaseTTSEngine):
    def __init__(self, model_name: str = "OvozifyLabs/matcha-tts-uz-v1"):
        self.model_name = model_name
        self.tts_client = None
        self.speaker_manager = SpeakerManager(Path(settings.speakers_dir))
        self.output_dir = Path(settings.audio_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_client(self):
        if self.tts_client is None:
            try:
                from TTS.api import TTS
            except ImportError as exc:
                raise RuntimeError("Install TTS from coqui-ai to use MatchaUzbekTTS") from exc
            self.tts_client = TTS(self.model_name, progress_bar=False, gpu=False)

    def synthesize(self, text: str, speaker_id: str) -> str:
        self._ensure_client()
        speaker = self.speaker_manager.get_speaker(speaker_id)
        if not speaker:
            raise RuntimeError(f"Unknown speaker: {speaker_id}")
        output_path = self.output_dir / f"tts_{speaker_id}_{os.getpid()}_{len(text)}.wav"
        wav = self.tts_client.tts(text, speaker=speaker_id if speaker_id != "default" else None)
        save_wav_bytes(wav, output_path)
        return str(output_path)

    def list_speakers(self) -> List[str]:
        return self.speaker_manager.list_speaker_ids()

    def add_speaker(self, speaker_id: str, speaker_config: dict) -> None:
        self.speaker_manager.add_speaker(**speaker_config)

    def remove_speaker(self, speaker_id: str) -> None:
        self.speaker_manager.remove_speaker(speaker_id)
