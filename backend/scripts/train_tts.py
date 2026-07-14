from pathlib import Path
import argparse

DESCRIPTION = "Train or fine-tune a TTS model on your Uzbek dataset."


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--data-dir", required=True, help="Processed audio speaker folder with wavs and metadata.csv")
    parser.add_argument("--output-dir", required=True, help="Output checkpoint directory")
    parser.add_argument("--model", default="uzlm/sayro-tts-1.7B")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()
    print("This script is a placeholder for TTS fine-tuning.\n"
          "Install a voice cloning/TTS training framework and update this script with a concrete training loop.\n"
          "Expected data: 5-10 minutes for minimal clone, 30-60 minutes for better quality, 2-5 hours for strong results.")
    print(f"data dir: {args.data_dir}")
    print(f"output dir: {args.output_dir}")
    print(f"model: {args.model}")
    print(f"epochs: {args.epochs}")
    print("See TRAINING_GUIDE.md for detailed steps.")


if __name__ == "__main__":
    main()
