from pathlib import Path
from pydub import AudioSegment
import argparse

DESCRIPTION = "Prepare and normalize Uzbek TTS dataset audio files."


def fix_audio_file(source_path: Path, target_path: Path, sample_rate: int = 22050):
    audio = AudioSegment.from_file(source_path)
    audio = audio.set_channels(1).set_frame_rate(sample_rate)
    audio.export(target_path, format="wav")


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--source", required=True, help="Source raw audio folder")
    parser.add_argument("--dest", required=True, help="Destination processed folder")
    parser.add_argument("--sample-rate", type=int, default=22050)
    args = parser.parse_args()
    source = Path(args.source)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    for audio_file in sorted(source.glob("**/*.*")):
        if audio_file.suffix.lower() not in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
            continue
        target_file = dest / audio_file.name
        fix_audio_file(audio_file, target_file, sample_rate=args.sample_rate)
        print(f"Converted: {audio_file} -> {target_file}")


if __name__ == "__main__":
    main()
