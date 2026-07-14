from pathlib import Path
import argparse
from app.tts.matcha_tts import MatchaUzbekTTS
from app.utils.text_cleaner import normalize_text

DESCRIPTION = "Benchmark TTS generation time for Uzbek text."


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--speaker", default="female_assistant", help="Speaker ID to use")
    args = parser.parse_args()
    tts = MatchaUzbekTTS()
    normalized = normalize_text(args.text)
    output = tts.synthesize(normalized, args.speaker)
    print(f"Synthesis completed: {output}")


if __name__ == "__main__":
    main()
