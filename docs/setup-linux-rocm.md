# SETUP_LINUX_ROCM

## Requirements

- Ubuntu 22.04+.
- AMD RX 7900 XTX or similar ROCm-compatible GPU.
- ROCm 6.x / 5.x installed.

## Install ROCm Python / PyTorch

1. Install ROCm system packages following AMD docs.
2. Install a ROCm-compatible Python environment:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm
```

## Install dependencies

```bash
cd /Users/shaxriyor/Desktop/local-ai-voice/backend
python -m pip install -r requirements.txt
```

## Run the API

```bash
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Notes

- Use `python -c "import torch; print(torch.cuda.is_available())"` to verify ROCm.
- If STT/TTS models require GPU memory, use smaller models.
- If using local LLM server with GPU, ensure the endpoint is configured in `.env`.
