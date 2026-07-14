# TRAINING_GUIDE

## How to train or fine-tune your own Uzbek voice

### Expected data amounts

- MVP: 5–10 minutes of high-quality voice data
- Better: 30–60 minutes
- Good: 2–5 hours
- Professional: 10–20+ hours

### Training workflow

1. Prepare processed audio and `metadata.csv`.
2. Install a compatible TTS training framework.
3. Configure your model and output path.
4. Run `python backend/scripts/train_tts.py --data-dir data/processed_audio/shahriyor --output-dir backend/models/tts/shahriyor`.

### Notes

- The current repo includes a training placeholder.
- Replace `train_tts.py` with model-specific training code once you install VITS/XTTS/StyleTTS2.
- Use `speaker.json` to register your new voice.

### Testing

- Use `python backend/scripts/infer_tts.py --text "Assalomu alaykum" --speaker shahriyor --output ./out.wav`.
- Play the file locally.
