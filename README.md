# uzbek-local-voice-ai

Local Uzbek voice assistant: speech-to-text, local LLM chat, and text-to-speech with multi-speaker support.

## What it does

- Converts Uzbek audio to text using local STT.
- Sends transcribed text to a local OpenAI-compatible LLM endpoint.
- Synthesizes Uzbek speech with configurable voices.
- Supports speaker profiles and dataset preparation for voice cloning.

## Quick start

1. Install dependencies:
   - `cd /Users/shaxriyor/Desktop/local-ai-voice/backend`
   - `python3 -m pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and update settings.
3. Run API:
   - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
4. Open the frontend after adding it.

## Models

- STT: `faster-whisper` primary; fallback to OpenAI Whisper.
- TTS: `OvozifyLabs/matcha-tts-uz-v1` via Coqui TTS.
- LLM: configured to local OpenAI-compatible API.

## Notes

- This repo is intended as a local/offline-first system.
- Some voice cloning training code is placeholder and requires model-specific frameworks.
- Mac users can use CPU/Metal. Linux users with ROCm should install ROCm-enabled PyTorch if using GPU models.
