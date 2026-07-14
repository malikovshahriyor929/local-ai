from pathlib import Path
from pydub import AudioSegment, silence
import argparse

DESCRIPTION = "Split long recordings into sentence-level wav files for Uzbek dataset preparation."


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--source", required=True, help="Source audio file or folder")
    parser.add_argument("--dest", required=True, help="Destination folder for split wavs")
    parser.add_argument("--silence-thresh", type=int, default=-40)
    parser.add_argument("--min-silence-len", type=int, default=500)
    parser.add_argument("--keep-silence", type=int, default=250)
    args = parser.parse_args()
    source = Path(args.source)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = [source] if source.is_file() else sorted(source.glob("**/*.*"))
    idx = 1
    for path in files:
        if path.suffix.lower() not in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
            continue
        audio = AudioSegment.from_file(path)
        segments = silence.split_on_silence(audio, min_silence_len=args.min_silence_len, silence_thresh=args.silence_thresh, keep_silence=args.keep_silence)
        for segment in segments:
            out_path = dest / f"{idx:06d}.wav"
            segment.export(out_path, format="wav")
            print(f"Saved {out_path}")
            idx += 1


if __name__ == "__main__":
    main()
