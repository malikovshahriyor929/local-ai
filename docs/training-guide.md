# TTS training guide

How to record a single-speaker Uzbek dataset and fine-tune a real voice from it.

## What actually gets trained

`backend/scripts/train_tts.py` trains a **VITS** acoustic model from scratch on your recordings,
using [Coqui TTS](https://github.com/idiap/coqui-ai-TTS)'s training stack. It does **not**
fine-tune `OvozifyLabs/matcha-tts-uz-v1` (that checkpoint's own training recipe isn't public) —
VITS-from-your-data is the standard, supported way to get a usable single-speaker voice out of
this stack. The resulting checkpoint is used independently of the `matcha` inference engine (it's
its own model, loaded by its own recipe — wiring it into `/speak` as a selectable engine is a
follow-up step, not done by the training script itself).

## Device reality (read this before choosing a machine)

`coqui-tts-trainer` hardcodes `.cuda()` calls throughout and has **no MPS support**. Concretely:

- **Windows PC (RX 7900 XTX)**: once you install ROCm-enabled PyTorch, `torch.cuda.is_available()`
  returns `True` on AMD GPUs too (ROCm exposes itself through the CUDA API — see
  [`../docs/windows-amd-setup.md`](windows-amd-setup.md) if present, or
  [`setup-linux-rocm.md`](setup-linux-rocm.md) as the closest reference). `train_tts.py` needs no
  code changes there — this is your real training machine.
- **MacBook (M-series)**: MPS is available for *inference* but not for this trainer. `--device
  auto` will detect this and fall back to CPU with a clear message. Use `--smoke-test` here to
  prove the pipeline works on a tiny run (minutes), not to train a usable voice (would take
  hours-to-days on CPU).

## Expected data amounts

- MVP / smoke test: a handful of sentences (just proves the pipeline runs)
- Minimal usable voice: 5-10 minutes
- Better: 30-60 minutes
- Good: 2-5 hours
- Professional: 10-20+ hours

## 1. Record your voice

```bash
cd backend
source venv/bin/activate
pip install -r requirements-dataset.txt   # sounddevice + soundfile, one-time
python scripts/record_dataset.py --speaker-id shahriyor
```

This reads one Uzbek sentence at a time from `backend/scripts/sentences_uz.py` (~50 sentences,
~5-10 minutes of reading), records your mic, and lets you `[a]ccept`, `[r]e-record`, `[p]lay back`,
`[s]kip`, or `[q]uit`. It warns (but doesn't block) on clipping, very quiet audio, or clips under
0.4s. The **first run asks for consent** and writes `data/consent/shahriyor.json` — recording is
refused without it. Progress is saved incrementally, so quitting and re-running resumes where you
left off. Bring your own sentence list with `--sentences-file my_sentences.txt` (one sentence per
line) for more/different coverage.

Output:

```
data/processed_audio/shahriyor/wavs/000001.wav ...
data/processed_audio/shahriyor/metadata.csv       # filename|transcript, one row per accepted clip
```

Validate what you've recorded any time via the API: `POST /dataset/validate {"speaker_id": "shahriyor"}`.

## 2. Train

```bash
pip install -r requirements-training.txt   # torch + coqui-tts, one-time, large download
python scripts/train_tts.py --speaker-id shahriyor --smoke-test
```

`--smoke-test` trims epochs/batch size/eval to the minimum that proves the pipeline works
end-to-end (dataset loads, model builds, a training + eval step runs, a checkpoint saves) in a
couple of minutes on CPU. It is **not** a usable voice — expect garbage audio out of a smoke-test
checkpoint. Run it once after recording to confirm everything is wired correctly before committing
to a real run.

For a real run, on the CUDA/ROCm machine:

```bash
python scripts/train_tts.py --speaker-id shahriyor --device cuda --epochs 1000 --batch-size 16
```

Useful flags:

| Flag | Purpose |
|---|---|
| `--device {auto,cuda,cpu}` | `auto` picks CUDA/ROCm if available, else warns and uses CPU |
| `--batch-size` | Start small (8-16) on a 24GB GPU and increase if VRAM allows |
| `--save-step` | How often (in steps) to checkpoint |
| `--resume-from <run-dir>` | Continue an interrupted run (pass the timestamped run directory under `--output-dir`) |
| `--data-dir` / `--output-dir` | Override the default `data/processed_audio/<speaker-id>` / `models/tts/<speaker-id>` locations |

Each run writes `run_meta.json` next to the checkpoints with the resolved config, dataset row
count, device, git commit, and installed package versions — check it if a run behaves unexpectedly
compared to a previous one. Checkpoints (`checkpoint_*.pth`, `best_model.pth`), `config.json`, and
TensorBoard event logs land under `models/tts/<speaker-id>/<run-name>-<timestamp>/`.

## 3. Listen to it

There's no dedicated `evaluate`/`export` command yet (see Known gaps in the root README). To
sanity-check a checkpoint manually, load it with Coqui's `TTS.tts.models.vits.Vits` +
`config.json` from the run directory, or use Coqui's own `tts` CLI:

```bash
tts --model_path models/tts/shahriyor/<run-dir>/best_model.pth \
    --config_path models/tts/shahriyor/<run-dir>/config.json \
    --text "Assalomu alaykum, bugun qandaysiz?" \
    --out_path out.wav
```

## Troubleshooting

- **`IndexError: LJSpeech format expects 3 pipe-delimited columns`**: shouldn't happen —
  `train_tts.py` uses its own `uzbek_pipe_formatter` for our 2-column `filename|text` format
  instead of Coqui's built-in `ljspeech` formatter. If you see this, you're likely calling Coqui's
  trainer directly instead of through `train_tts.py`.
- **`ImportError: cannot import name 'isin_mps_friendly'`**: your `transformers` version is too
  new for this `coqui-tts` release. `requirements-training.txt` pins a known-good version
  (`transformers==4.57.6`) — reinstall from it rather than the latest.
- **Training silently uses CPU on the Windows PC**: `torch.cuda.is_available()` is `False`, which
  means ROCm-enabled PyTorch isn't actually installed/active — see `setup-linux-rocm.md` (or your
  ROCm-on-Windows install docs) and re-check `python -c "import torch; print(torch.cuda.is_available())"`.
- **Out of memory on the 24GB GPU**: lower `--batch-size` first; there is no automatic
  batch-size-reduction-and-retry in `train_tts.py` yet (see Known gaps in the root README) — retry
  manually with a smaller value.
