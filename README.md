# uzbek-local-voice-ai

Local, offline-first Uzbek voice assistant: speech-to-text (STT), a local LLM chat step, and
text-to-speech (TTS) with per-speaker voice profiles. Everything runs on your own machine —
no cloud API keys required for the core loop.

- **STT**: `faster-whisper` (primary) or plain `openai-whisper` (fallback), Uzbek-language transcription.
- **LLM**: any local OpenAI-compatible chat endpoint (Ollama, LM Studio, vLLM, etc.).
- **TTS**: `OvozifyLabs/matcha-tts-uz-v1` via Coqui `TTS`, with named speaker profiles.
- **Speakers**: JSON profiles under `data/speakers/`, extendable for voice cloning/fine-tuning later.

This document is the single source of truth for running and operating the project. Deeper,
narrower guides live in [`docs/`](docs/) and are linked from the relevant section below.

## 1. Repository layout

```
local-ai-voice/
├── backend/                 Python FastAPI service (STT, LLM bridge, TTS, speakers)
│   ├── app/
│   │   ├── main.py          FastAPI app + routes
│   │   ├── config.py        Settings loaded from .env (pydantic-settings)
│   │   ├── stt/              faster-whisper / whisper / kotib (whisper-jax) engines
│   │   ├── tts/               Matcha (Coqui TTS) engine
│   │   ├── llm/                OpenAI-compatible chat client
│   │   ├── speakers/          Speaker profile manager (data/speakers/*.json)
│   │   ├── vad/                WebRTC VAD helper
│   │   └── utils/              Text normalization, audio helpers
│   ├── scripts/              CLI utilities: dataset prep, benchmarking, inference, training stub
│   ├── requirements.txt / pyproject.toml
│   └── .env / .env.example (project-root .env.example is the template you copy)
├── frontend/                 Vite + React + TypeScript + Tailwind web UI (talks to backend on :8000)
│   └── src/
│       ├── App.tsx            Layout: speaker select, orb, transcript/answer, manual panel
│       ├── components/
│       │   └── VoiceOrb.tsx   Click-to-talk mic capture + canvas visualizer + /voice-chat
│       └── lib/                 Typed API client (api.ts) + WAV encoder (wav.ts)
├── data/
│   ├── speakers/              One folder per speaker, each with speaker.json
│   ├── processed_audio/       Prepared per-speaker datasets (wavs/ + metadata.csv)
│   └── audio_output/          Generated TTS output (git-ignored)
├── docs/                      Setup, dataset, training, API, and troubleshooting guides
├── scripts/                   Reserved for future top-level automation (currently empty)
├── .env.example               Copy to backend/.env before running the API
└── README.md                  This file
```

> **Note on project history**: this repo previously also contained an unfinished TypeScript
> (`apps/api` + `apps/web`) rewrite and a standalone Gradio demo (`app.py`). Both were removed
> during cleanup because they were not functional (mocked endpoints, empty model runner) and not
> documented — `backend/` + `frontend/` is the one real, working stack. The full pre-cleanup state
> is preserved in git history (`git log`, first commit) if you ever need to recover something from
> it.

## 2. Prerequisites

| Requirement | Why |
|---|---|
| Python **3.11+** | `backend/pyproject.toml` pins `python = "^3.11"`. Older versions (this repo previously shipped with a stale 3.9 venv — deleted, see above) will not resolve all dependencies correctly. |
| Node.js 18+ and `npm` | To run `frontend/`. |
| `ffmpeg` | Required by `pydub` for any audio format conversion (dataset prep, normalization scripts). |
| A local OpenAI-compatible LLM server (optional) | Only needed for `/chat` and `/voice-chat`. E.g. `ollama serve` with a pulled model. |

Platform-specific accelerator notes (Apple Silicon MPS/CPU, AMD ROCm on Linux):

- [`docs/setup-mac.md`](docs/setup-mac.md)
- [`docs/setup-linux-rocm.md`](docs/setup-linux-rocm.md)
- Windows + AMD ROCm is **not yet documented** — ROCm's Windows support is narrower than Linux's;
  if you need it, the Linux ROCm guide is the closest reference and WSL2 + ROCm is currently the
  more realistic path. Treat this as a known gap, not a supported path.

## 3. Quick start

```bash
# 1. Create a fresh virtualenv with Python 3.11+ (do not reuse an old/mismatched venv)
cd backend
python3.11 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install backend dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 3. Configure environment
cd ..
cp .env.example backend/.env    # edit backend/.env to taste (LLM URL/model, default speaker, ...)

# 4. Run the API (from backend/, so the relative data paths in .env resolve correctly)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify it's alive:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/speakers
```

In a second terminal, run the web UI:

```bash
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

> **Do not open `frontend/index.html` directly or via a static file server (e.g. VS Code "Live
> Server" on port 5500).** This is a Vite + React + TypeScript app — the browser needs Vite's dev
> server to compile `.tsx` on the fly. Opening the raw HTML file serves an unprocessed
> `<script src="/src/main.tsx">` that no browser can execute. Always use `npm run dev` and open
> the URL Vite prints (`http://localhost:5173` by default; Vite listens on `::1`/`localhost`, so
> use `localhost`, not `127.0.0.1`, if you ever curl it).

The frontend talks to `http://localhost:8000` by default (see `frontend/src/lib/api.ts`; override
with a `VITE_API_BASE` env var if you run the backend elsewhere), so the backend must be running
first.

### Click-to-talk voice UI

The home page centers on an animated orb (`frontend/src/components/VoiceOrb.tsx`, canvas-based,
reacts to your mic volume in real time — no external animation library):

1. Click the orb → it requests microphone access and starts recording (browser will prompt for
   mic permission the first time).
2. Speak. The orb pulses with your voice; it auto-stops ~1.6s after you stop talking, or you can
   click again to stop manually.
3. The recorded WAV is sent to `POST /voice-chat`, which runs **STT → local LLM → TTS** in one
   round trip using the models configured in `backend/.env`.
4. The transcript and the AI's text answer appear below the orb, and the synthesized reply audio
   plays automatically.

This requires all three pieces to be reachable: the configured STT engine's dependency installed,
a local LLM server running at `LLM_BASE_URL` (e.g. `ollama serve`), and `TTS_ENGINE`'s dependency
installed. If any step fails, the orb turns red and shows the error message instead of silently
hanging — check the `uvicorn` terminal for the underlying traceback.

A collapsible "Qo'lda boshqarish" (manual control) panel below the orb also exposes plain text
chat and file-upload transcription independently, for testing STT or TTS in isolation.

**Important — engine dependencies are installed separately.** `backend/requirements.txt` only
pulls in the FastAPI service itself. The actual STT/TTS engines are optional, heavier
dependencies you install based on which engine you configure in `.env`:

| `.env` setting | Extra package to install | Notes |
|---|---|---|
| `STT_ENGINE=faster-whisper` (default) | `pip install faster-whisper` | Uses `openai/whisper-small` by default; CTranslate2-based, fast on CPU. |
| `STT_ENGINE=whisper` | `pip install openai-whisper` | Reference fallback implementation. |
| `STT_ENGINE=kotib` | `pip install whisper-jax` | Experimental JAX-based engine (`backend/app/stt/kotib_stt.py`); expect rough edges. |
| `TTS_ENGINE=matcha` (default, only option implemented) | `pip install TTS` (Coqui) | Loads `OvozifyLabs/matcha-tts-uz-v1`. First run downloads the model from Hugging Face. |

The app will raise a clear `RuntimeError` telling you which package to install if you hit an
endpoint before installing the matching engine dependency — it will not silently fall back or crash
with an opaque `ImportError`.

## 4. Configuration (`backend/.env`)

Copied from `.env.example` (project root) into `backend/.env`. All paths are resolved **relative to
the `backend/` directory**, because that's where you run `uvicorn` from:

```
STT_ENGINE=faster-whisper          # faster-whisper | whisper | kotib
STT_LANGUAGE=uz
TTS_ENGINE=matcha                  # matcha is the only implemented engine today
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=gpt-oss:20b              # any model your local server exposes
DEFAULT_SPEAKER=female_assistant
AUDIO_OUTPUT_DIR=../data/audio_output
SPEAKERS_DIR=../data/speakers
PROCESSED_AUDIO_DIR=../data/processed_audio
SYSTEM_PROMPT=Siz tabiiy va hurmatli o'zbek tilida javob beradigan lokal yordamchisiz. ...
```

## 5. API reference

Full endpoint-by-endpoint docs: [`docs/api.md`](docs/api.md). Summary:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + which STT engine / LLM URL are configured |
| GET | `/speakers` | List speaker profiles |
| POST | `/stt/file` | Upload an audio file, get back a normalized Uzbek transcript |
| POST | `/stt/mic-chunk` | Transcribe a short raw microphone chunk |
| POST | `/chat` | Send text to the configured local LLM |
| POST | `/speak` | Synthesize text as a given speaker, returns an audio URL |
| POST | `/voice-chat` | STT → LLM → TTS in one round trip |
| POST | `/speakers/add` | Register a new speaker profile |
| POST | `/dataset/validate` | Validate a speaker's `processed_audio/<id>/metadata.csv` against its wavs |

Interactive Swagger docs are also served at `http://localhost:8000/docs` while the API is running.

## 6. Managing speakers

Speakers are just a folder + JSON file under `data/speakers/<speaker_id>/speaker.json`:

```json
{
  "speaker_id": "shahriyor",
  "display_name": "Shahriyor Voice",
  "type": "cloned_or_finetuned",
  "language": "uz",
  "reference_audio": "reference.wav",
  "model_path": "models/tts/shahriyor",
  "permission": "owned_by_user"
}
```

Add one via the API instead of hand-editing files:

```bash
curl -X POST http://localhost:8000/speakers/add \
  -H "Content-Type: application/json" \
  -d '{"speaker_id": "shahriyor", "display_name": "Shahriyor Voice"}'
```

**Consent / ownership**: only register a speaker whose voice you own or have explicit permission
to use — `permission` in `speaker.json` exists to record that. Don't commit real people's raw
recordings to git (audio files are already excluded via `.gitignore`); dataset ownership and
consent are the operator's responsibility, not something the code enforces for you today.

## 7. Dataset preparation & fine-tuning

See [`docs/dataset-guide.md`](docs/dataset-guide.md) for recording requirements and the
`metadata.csv` format, and [`docs/training-guide.md`](docs/training-guide.md) for the fine-tuning
workflow.

CLI scripts (run from `backend/`, with the venv active):

```bash
python scripts/prepare_dataset.py --source ../data/raw_audio --dest ../data/processed_audio/shahriyor/wavs
python scripts/split_audio.py --source <long_recording.wav> --dest ../data/processed_audio/shahriyor/wavs
python scripts/normalize_audio.py --source <in_dir> --dest <out_dir>
python scripts/transcribe_dataset.py --source ../data/processed_audio/shahriyor/wavs --output ../data/processed_audio/shahriyor/metadata.csv
python scripts/infer_tts.py --text "Assalomu alaykum" --speaker shahriyor --output ./out.wav
python scripts/benchmark_stt.py --audio-dir <wav_dir>
python scripts/benchmark_tts.py --text "Assalomu alaykum" --speaker female_assistant
```

**`scripts/train_tts.py` is a documented placeholder**, not a working trainer — it prints the data
requirements and exits. Fine-tuning a real Uzbek voice-cloning model (VITS/XTTS/StyleTTS2/etc.)
needs a model-specific training loop that isn't implemented here yet; treat this as the next real
engineering task if you want single-speaker fine-tuning, not something you can run today.

## 8. Day-to-day operation / management

- **Start backend**: `cd backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- **Start frontend**: `cd frontend && npm run dev`
- **Stop either**: `Ctrl+C` in its terminal (or `pkill -f "uvicorn app.main:app"`).
- **Check what's configured**: `curl http://localhost:8000/health`
- **Update backend deps**: edit `backend/requirements.txt` (or `pyproject.toml`) and re-run
  `pip install -r requirements.txt` inside the venv.
- **Reset generated audio**: safe to delete everything under `data/audio_output/` — it's
  regenerated on demand and already git-ignored.
- **Version control**: this repo is now a git repository (it wasn't before cleanup). Normal git
  workflow applies — `git status`, `git add`, `git commit`. `venv/`, `node_modules/`, `.env`,
  generated audio, and raw dataset audio are git-ignored on purpose; don't force-add them.
- **Logs**: `uvicorn --reload` logs to stdout of whichever terminal runs it; there's no separate
  log file yet.

## 9. Troubleshooting

Common issues and fixes: [`docs/troubleshooting.md`](docs/troubleshooting.md). If the backend
fails to start, read the traceback — this project intentionally raises clear `RuntimeError`s for
missing optional engine packages rather than failing silently.

## 10. Known gaps (be aware, don't assume otherwise)

- `scripts/train_tts.py` is a placeholder, not a real trainer (see §7).
- No automated test suite exists yet (`pytest` is a listed dev dependency but no tests are checked in).
- No Windows+AMD ROCm setup guide yet.
- `kotib` STT engine (`whisper-jax`) is experimental and less exercised than `faster-whisper`.
- Voice cloning / multi-speaker fine-tuning is not implemented — only inference against
  pre-existing speaker profiles works today.
