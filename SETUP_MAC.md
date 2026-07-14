# SETUP_MAC

## Requirements

- macOS 14+ on Apple Silicon.
- Python 3.11+.
- Homebrew.
- `ffmpeg` installed via `brew install ffmpeg`.

## Install

```bash
cd /Users/shaxriyor/Desktop/local-ai-voice/backend
python3 -m pip install -r requirements.txt
```

## Optional model packages

- `faster-whisper` for STT.
- `TTS` for Uzbek TTS.
- `whisper-jax` if using Kotib STT.

## Run

```bash
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Notes

- Apple Silicon can run local models on CPU/Metal through PyTorch.
- If using `faster-whisper`, the library will auto-select device.
- For large TTS models, use a smaller model if Mac memory is limited.
