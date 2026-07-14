import json
from pathlib import Path
from typing import List, Optional

class SpeakerManager:
    def __init__(self, speakers_dir: Path):
        self.speakers_dir = speakers_dir
        self.speakers_dir.mkdir(parents=True, exist_ok=True)

    def _speaker_file(self, speaker_id: str) -> Path:
        return self.speakers_dir / speaker_id / "speaker.json"

    def list_speakers(self) -> List[dict]:
        speakers = []
        for speaker_path in self.speakers_dir.iterdir():
            if speaker_path.is_dir():
                config_path = speaker_path / "speaker.json"
                if config_path.exists():
                    with config_path.open("r", encoding="utf-8") as f:
                        speakers.append(json.load(f))
        return speakers

    def list_speaker_ids(self) -> List[str]:
        return [speaker["speaker_id"] for speaker in self.list_speakers()]

    def get_speaker(self, speaker_id: str) -> Optional[dict]:
        config_path = self._speaker_file(speaker_id)
        if not config_path.exists():
            return None
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def add_speaker(self, speaker_id: str, display_name: str, reference_audio: str = "reference.wav", model_path: str = "", language: str = "uz", permission: str = "owned_by_user") -> None:
        speaker_dir = self.speakers_dir / speaker_id
        speaker_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "speaker_id": speaker_id,
            "display_name": display_name,
            "type": "cloned_or_finetuned",
            "language": language,
            "reference_audio": reference_audio,
            "model_path": model_path,
            "permission": permission,
        }
        with (speaker_dir / "speaker.json").open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def remove_speaker(self, speaker_id: str) -> None:
        speaker_dir = self.speakers_dir / speaker_id
        if speaker_dir.exists():
            for child in speaker_dir.iterdir():
                if child.is_file():
                    child.unlink()
                else:
                    for subchild in child.iterdir():
                        subchild.unlink()
                    child.rmdir()
            speaker_dir.rmdir()

    def validate_dataset(self, speaker_id: str):
        from pathlib import Path
        speaker_data = self.speakers_dir.parent / "processed_audio" / speaker_id
        metadata_path = speaker_data / "metadata.csv"
        if not metadata_path.exists():
            raise FileNotFoundError("metadata.csv not found")
        records = []
        with metadata_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|", 1)
                if len(parts) != 2:
                    raise ValueError(f"Invalid metadata line: {line}")
                wav_file, transcript = parts
                wav_path = speaker_data / "wavs" / wav_file
                if not wav_path.exists():
                    raise FileNotFoundError(f"Missing wav file: {wav_file}")
                records.append({"wav": wav_file, "text": transcript})
        return records
