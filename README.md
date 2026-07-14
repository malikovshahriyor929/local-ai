# Uzbek Local Voice AI

A self-contained local Uzbek voice-assistant workspace. It runs the LLM, STT, and TTS inside this repository after the corresponding model files have been downloaded. It does not require Ollama, LM Studio, OpenAI, Anthropic, or a cloud AI API.

## Current vertical slice

- Direct GGUF inference from `models/llm/model.gguf` through `llama-cpp-python`; the model is held in memory and streams tokens.
- A project-local llama.cpp server fallback is buildable at `tools/llama.cpp/`; no system-wide binary is assumed.
- Direct local NeMo FastConformer STT and Qwen3 TTS adapters, including browser WebM conversion through FFmpeg.
- Next.js 16 App Router UI with microphone recording, staged voice-chat SSE, playback, cancellation, and local system/model status.
- Explicit Hugging Face model downloader, offline-mode guard, model manifest, hardware diagnostics, Prisma schema, and unit tests that do not load models.

## First run

Prerequisites: Node 22+, pnpm, Python 3.11+, [uv](https://docs.astral.sh/uv/), FFmpeg, CMake, Git, and a C/C++ compiler. On Windows AMD, install a current Vulkan-capable AMD driver.

```bash
pnpm run setup
pnpm models:download list
pnpm models:download download-llm
pnpm models:download download-stt
pnpm models:download download-tts
pnpm models:verify
pnpm dev
```

The downloader asks for confirmation before every large transfer, supports Hugging Face tokens through `HF_TOKEN`, and keeps weights under `models/`. Use `OFFLINE_MODE=true` only after required files are present; in that mode no model hub is contacted.

Open `http://127.0.0.1:3000`. The browser speaks only to Next.js routes; those routes proxy to the internal service at `127.0.0.1:8001`.

## Commands

| Command | Purpose |
| --- | --- |
| `pnpm run setup` | Prepare dependencies, local llama.cpp, Prisma, and optionally models |
| `pnpm dev` | Start Next.js and internal AI service together |
| `pnpm dev:web` / `pnpm dev:ai` | Start one project service |
| `pnpm dev:llm` | Optional project-managed llama.cpp server fallback |
| `pnpm health` | Query the Next.js system-health proxy |
| `pnpm models:download list` | List model choices and sizes |
| `pnpm models:verify` | Check local model paths |
| `pnpm test` | Unit tests only, without large models |

## Model layout

`configs/models.yaml` is the one source of model definitions. Default paths are `models/llm/model.gguf`, `models/stt/fastconformer`, `models/tts/uzbek-voice` (fine-tuned replacement) and `models/tts/qwen3-tts-base` (development base model).

The default LLM is configurable and set to a multilingual Qwen GGUF Q4_K_M option. Set `LLM_GPU_LAYERS=-1` for acceleration when the installed llama-cpp-python wheel was built for Metal/Vulkan/HIP; otherwise the engine falls back to CPU. `pnpm setup` builds the server fallback with Metal on Apple Silicon and Vulkan on Linux/Windows AMD.

## Honest integration status

No model weights are included in Git, and this checkout has not generated a real LLM response, Uzbek transcription, TTS audio file, or complete voice-loop result. Run the downloads and then the separate real integration checks before treating those capabilities as verified. The unit tests intentionally mock/avoid large models.

See [Windows AMD setup](docs/setup-windows-amd.md), [macOS setup](docs/setup-mac.md), and [troubleshooting](docs/troubleshooting.md).
