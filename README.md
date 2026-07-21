# Uzbek Local Voice AI

A self-contained local Uzbek voice-assistant workspace. It runs the LLM, STT, and TTS inside this repository after the corresponding model files have been downloaded. It does not require Ollama, LM Studio, OpenAI, Anthropic, or a cloud AI API.

## Current vertical slice

- Direct GGUF inference from `models/llm/model.gguf` through `llama-cpp-python`; the model is held in memory and streams tokens.
- A project-local llama.cpp server fallback is buildable at `tools/llama.cpp/`; no system-wide binary is assumed.
- Mac control from Uzbek speech or text: a command is planned, announced aloud ("Safari dasturini ochaman"), then executed. A deterministic parser handles common commands instantly; anything else goes to the local LLM constrained to the ActionPlan JSON schema. Every step is whitelist-validated before it runs.
- Hybrid local STT: Uzbek FastConformer first, automatic faster-whisper large-v3 fallback when it returns nothing (`STT_ENGINE=hybrid|fastconformer|whisper`). All input is normalised to 16 kHz mono through FFmpeg.
- Dual local TTS: built-in Uzbek MMS voice by default (no reference recording needed; Latin text transliterated to Cyrillic, numbers expanded to words), with Qwen3 voice cloning / fine-tuned checkpoints for explicitly chosen speakers (`TTS_ENGINE=auto|mms|qwen3`).
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

## Mac control

Say or type a command and the assistant states what it is about to do, speaks that sentence, then performs it. Questions are still answered as normal chat — only recognised commands are executed.

| Command | Runs |
| --- | --- |
| `Safari och` / `open safari` / `chrome och` | Opens the app |
| `musiqa qo'y`, `pauza`, `keyingi qo'shiq` | Spotify or Music playback |
| `toshkent ob-havosi qidir`, `search for X` | Web search in the default browser |
| `yangi tab`, `nusxa ol`, `saqla` | Keyboard shortcut in the frontmost app |

Safety boundary: the model never runs code. It only proposes an `ActionPlan`, which `apps/ai-service/app/actions/plan.py` validates against a fixed whitelist before `executor.py` performs it. Apps outside the list, non-`http(s)` URLs, unknown media/shortcut values, and anything the schema does not define are rejected. No step is ever passed to a shell, and file deletion, purchases, and system settings are not expressible in the schema at all.

`shortcut` and `typeText` drive System Events, so the AI service's host process needs Accessibility permission (System Settings → Privacy & Security → Accessibility). Opening apps, URLs, searches, and media control do not need it.

Endpoints: `POST /api/actions/plan` returns a validated plan without running it; `POST /api/actions/execute` runs one. Plans marked `requiresConfirmation` are not executed until the request repeats with `confirmed: true`.

## Model layout

`configs/models.yaml` is the one source of model definitions. Default paths are `models/llm/model.gguf`, `models/stt/fastconformer`, `models/stt/whisper-large-v3` (hybrid STT fallback, `download-stt-whisper`), `models/tts/mms-uzbek` (default built-in Uzbek voice, `download-tts-mms`), `models/tts/uzbek-voice` (fine-tuned replacement) and `models/tts/qwen3-tts-base` (cloning base model).

The default LLM is configurable and set to a multilingual Qwen GGUF Q4_K_M option. Set `LLM_GPU_LAYERS=-1` for acceleration when the installed llama-cpp-python wheel was built for Metal/Vulkan/HIP; otherwise the engine falls back to CPU. `pnpm run setup` builds the server fallback with Metal on Apple Silicon and Vulkan on Linux/Windows AMD.

The default conversation voice is the built-in MMS Uzbek speaker (`facebook/mms-tts-uzb-script_cyrillic`, ~0.2 GB): it needs no reference recording, synthesises several times faster than real time on CPU, and Latin input is transliterated to Cyrillic automatically (numbers are expanded to spoken words through `packages/uzbek-text`).

The supplied Qwen3-TTS **Base** checkpoint (0.6B) does zero-shot voice cloning from a short WAV,
not a built-in Uzbek voice — see [`docs/tts-finetuning.md`](docs/tts-finetuning.md) for cloning
vs. real fine-tuning (which needs the separate 1.7B-Base checkpoint,
`download-tts-finetune-base`, and has a different, incompatible tensor shape from the 0.6B one —
do not assume they're interchangeable). Cloning is used when a clone speaker is explicitly
requested or activated (or with `TTS_ENGINE=qwen3`). In the default `TTS_ENGINE=auto` mode a
missing reference recording no longer blocks speech: synthesis falls back to the MMS voice
instead of returning `TTS_REFERENCE_AUDIO_NOT_FOUND`.

## Honest integration status

No model weights are included in Git. Verified end-to-end on the current Mac setup (2026-07-21):

- Mac control is verified for real, not just planned: speaking `Safari och` into `/api/voice-chat` transcribed correctly, produced the plan `Safari dasturini ochaman`, spoke it, and actually launched Safari. Typing the same command in the web UI did the same, showing `✓ Safari ochildi` under the answer. A normal question (`O'zbekiston poytaxti qayer?`) was answered as chat rather than executed.
- Safety rejections are verified: `Keychain Access` and `file:///etc/passwd` are both refused with `PLAN_REJECTED` before anything runs.
- `/api/tts/synthesize` with the default speaker produces real MMS Uzbek audio (~10 s of speech in ~2.7 s including model load) and `speakerId: "user_voice"` still produces real cloned-voice audio through Qwen3.
- STT round-trip is verified: MMS-generated Uzbek speech transcribed by FastConformer comes back word-for-word. The hybrid fallback is verified too — a 37 s recording on which FastConformer returns an empty hypothesis now comes back as a full Whisper transcript instead of an error.
- FastConformer alone can still return empty hypotheses on some real recordings (this is why hybrid mode is the default), and Whisper's Uzbek accuracy is noticeably below FastConformer's on clean speech — treat Whisper output as a fallback transcript.
- The downloaded Qwen GGUF streams real responses through the Next.js chat proxy.
- The fine-tuning pipeline (`scripts/train_tts_uzbek.py`) has its data preparation step verified
  working with the 1.7B-Base model on this Mac, but the training step itself ran out of memory
  partway through (full AdamW fine-tuning of a 1.7B model in fp32 needs ~27GB+, more than this
  Mac's 24GB unified memory) — it has **not** completed a training run or saved a checkpoint on
  this machine; that needs a CUDA/ROCm GPU with dedicated VRAM (see `docs/tts-finetuning.md`).
- The unit tests intentionally avoid loading large models.

See [Windows AMD setup](docs/setup-windows-amd.md), [macOS setup](docs/setup-mac.md),
[troubleshooting](docs/troubleshooting.md), and [TTS cloning/fine-tuning](docs/tts-finetuning.md).
