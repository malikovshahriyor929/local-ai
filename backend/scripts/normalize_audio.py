from pathlib import Path
from pydub import AudioSegment
import argparse

DESCRIPTION = "Normalize waveform loudness and format for dataset audio."


def normalize_audio_file(source_path: Path, target_path: Path, sample_rate: int = 22050, target_dbfs: float = -20.0):
    audio = AudioSegment.from_file(source_path)
    audio = audio.set_frame_rate(sample_rate).set_channels(1)
    change_dbfs = target_dbfs - audio.dBFS
    normalized = audio.apply_gain(change_dbfs)
    normalized.export(target_path, format="wav")


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--source", required=True, help="Source folder")
    parser.add_argument("--dest", required=True, help="Destination folder")
    parser.add_argument("--sample-rate", type=int, default=22050)
    parser.add_argument("--target-dbfs", type=float, default=-20.0)
    args = parser.parse_args()
    source = Path(args.source)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    for audio_file in sorted(source.glob("**/*.*")):
        if audio_file.suffix.lower() not in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
            continue
        target_file = dest / audio_file.name
        normalize_audio_file(audio_file, target_file, sample_rate=args.sample_rate, target_dbfs=args.target_dbfs)
        print(f"Normalized: {audio_file} -> {target_file}")


if __name__ == "__main__":
    main()
