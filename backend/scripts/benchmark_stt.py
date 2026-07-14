import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.stt.whisper_stt import FasterWhisperSTT
from app.utils.text_cleaner import normalize_text

DESCRIPTION = "Benchmark STT model speed and basic audio transcription accuracy."


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--audio-dir", required=True, help="Directory containing wav test files")
    parser.add_argument("--model", default="openai/whisper-small")
    args = parser.parse_args()
    stt = FasterWhisperSTT(model_name=args.model)
    for audio_file in sorted(Path(args.audio_dir).glob("*.wav")):
        text = stt.transcribe_file(str(audio_file), language="uz")
        print(f"{audio_file.name} -> {normalize_text(text)}")


if __name__ == "__main__":
    main()
