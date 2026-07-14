from pathlib import Path
import argparse
from app.stt.whisper_stt import FasterWhisperSTT

DESCRIPTION = "Generate transcripts for a folder of Uzbek dataset audio files."


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--source", required=True, help="Source audio folder")
    parser.add_argument("--output", required=True, help="Output metadata.csv path")
    parser.add_argument("--model", default="openai/whisper-small")
    args = parser.parse_args()
    stt = FasterWhisperSTT(model_name=args.model)
    metadata_path = Path(args.output)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("w", encoding="utf-8") as out_file:
        for audio_file in sorted(Path(args.source).glob("*.wav")):
            transcript = stt.transcribe_file(str(audio_file), language="uz")
            out_file.write(f"{audio_file.name}|{transcript}\n")
            print(f"{audio_file.name}: {transcript}")


if __name__ == "__main__":
    main()
