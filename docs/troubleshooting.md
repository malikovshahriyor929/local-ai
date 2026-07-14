# TROUBLESHOOTING

## Model download problems

- If `faster-whisper` cannot download, check internet access and use `hf_token` if model is gated.
- For Coqui TTS, install `TTS` and verify the model name.

## CUDA vs ROCm issues

- On Linux ROCm, ensure `torch` is installed from ROCm wheels.
- On macOS, use CPU/Metal-friendly packages.

## AMD GPU issues

- Use `python -c "import torch; print(torch.cuda.is_available())"`.
- Lower batch size or use smaller models if VRAM is insufficient.

## Out of memory

- Use smaller STT/TTS models.
- Set `USE_INT8=1` for `faster-whisper`.

## Bad Uzbek pronunciation

- Normalize text with `app.utils.text_cleaner.normalize_text`.
- Use Uzbek-specific models rather than generic English voices.

## Noisy output

- Ensure source audio is clean and mono.
- Use `backend/scripts/normalize_audio.py`.

## Slow STT/TTS

- Use smaller models if local hardware is limited.
- Prefer `faster-whisper` with `int8` on CPU.
