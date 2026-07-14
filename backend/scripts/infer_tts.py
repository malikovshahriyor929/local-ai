import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tts.matcha_tts import MatchaUzbekTTS
from app.utils.text_cleaner import normalize_text

DESCRIPTION = "Run TTS inference for a given text and speaker."


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--speaker", default="female_assistant", help="Speaker ID to use")
    parser.add_argument("--output", default="./output.wav", help="Output wav file path")
    args = parser.parse_args()
    tts = MatchaUzbekTTS()
    normalized = normalize_text(args.text)
    output_path = tts.synthesize(normalized, args.speaker)
    print(f"Saved output to {output_path}")


if __name__ == "__main__":
    main()
