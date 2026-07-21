# TTS: voice cloning vs. fine-tuning for Uzbek

Two different things live under "make the TTS sound like a specific person," and this stack
supports both differently. Read this before assuming either one is what you need.

## 1. Zero-shot voice cloning (works today, no training)

`Qwen/Qwen3-TTS-12Hz-0.6B-Base` (already downloaded, `models/tts/qwen3-tts-base/`) does **3-second
voice cloning**: give it one short reference clip of a voice and it can speak arbitrary text in
that voice immediately - no training loop, no dataset, no GPU required (runs on CPU/MPS/CUDA/ROCm
alike, just slower without a real GPU).

This is what `POST /api/tts/synthesize` already uses. `speakerId: "default"` resolves to
`data/speakers/user_voice/reference.wav` if you've recorded one (see the consent-based recording
flow in the web UI, or `scripts/record_reference_voice.py`), otherwise falls back to
`female_assistant`.

**Verified working 2026-07-14**: real 5.44s audio generated from `speakerId: "default"` using a
recorded `user_voice` reference clip, ~15.5s generation time on an M-series Mac (Metal backend).

This is almost certainly what you want for "make it sound like me." Fine-tuning below is for a
different, heavier use case.

## 2. Fine-tuning (real training, needs a GPU for real use)

Fine-tuning bakes a specific voice into a **new checkpoint** as a named "custom voice" (via
`generate_custom_voice()`), rather than cloning from a reference clip at inference time. It's what
you'd want for: consistently better quality than zero-shot cloning gets you, or a checkpoint that
doesn't need a reference clip at inference time at all.

### The official recipe, vendored

`apps/ai-service/finetuning/` vendors Qwen's own fine-tuning scripts
(`dataset.py`, `prepare_data.py`, `sft_12hz.py`, Apache-2.0,
[github.com/QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS/tree/main/finetuning)), not a
reimplementation - see `apps/ai-service/finetuning/README.md` for exactly what was changed
(CUDA-only hardcoding made configurable; one real upstream bug fixed) and what wasn't.

### The model-size trap (read this before running anything)

**Fine-tuning only works with the 1.7B-Base checkpoint, not the 0.6B-Base one**, even though both
are described upstream as "capable of fine-tuning." Verified 2026-07-14 by loading both models'
`config.json` and the actual `model.safetensors` tensor shapes:

| | 0.6B-Base | 1.7B-Base |
|---|---|---|
| `talker.model.text_embedding.weight` | `[151936, 2048]` | `[151936, 2048]` |
| `talker.model.codec_embedding.weight` | `[3072, 1024]` | `[3072, 2048]` |
| `talker_config.hidden_size` | 1024 | 2048 |

`sft_12hz.py` does `input_text_embedding + input_codec_embedding` - on the 0.6B model this is a
2048-dim tensor plus a 1024-dim tensor, which crashes with `RuntimeError: The size of tensor a
(2048) must match the size of tensor b (1024)`. This is a real architecture property of the
checkpoints, not a bug in this project's code. `configs/models.yaml` has a `tts.finetune_base`
entry for the 1.7B model (`models/tts/qwen3-tts-1.7b-base/`, ~4.3GB) - download it with:

```bash
uv run --project apps/ai-service python scripts/download_models.py download-tts-finetune-base
```

The 0.6B model stays exactly what `/api/tts/synthesize` uses for zero-shot cloning; nothing about
that path changes.

### Device reality

`sft_12hz.py` upstream hardcodes `attn_implementation="flash_attention_2"` (NVIDIA-CUDA-only
kernel) and `torch_dtype=torch.bfloat16` / `mixed_precision="bf16"`. The vendored copy makes these
CLI flags (`--attn_implementation`, `--dtype`, `--mixed_precision`) that auto-pick safer defaults
per device:

- **CUDA/ROCm** (`torch.cuda.is_available()` - true on both real NVIDIA and ROCm-enabled AMD,
  including the RX 7900 XTX once ROCm PyTorch is installed): `bf16`, `sdpa` by default (opt into
  `flash_attention_2` explicitly once you've confirmed it's installed and working).
- **Mac (MPS)**: falls back to `fp32`/no mixed precision. `sft_12hz.py` pokes at custom model
  internals (`model.speaker_encoder(...)`, `model.talker.code_predictor.get_input_embeddings()`,
  `forward_sub_talker_finetune(...)`) that have no guaranteed MPS kernel support.

  **Verified 2026-07-14 on a 24GB M-series Mac**: `prepare_data.py` (audio code extraction)
  succeeds on MPS. `sft_12hz.py` loads the 1.7B model and starts training, but full AdamW in fp32
  needs roughly 4x the parameter memory (weights + gradients + 2 optimizer moments ≈ 27GB+) before
  activations - it exceeded this machine's 24GB unified memory, the process went into heavy
  swapping (17GB resident, system down to ~176MB free, `%CPU` near zero from thrashing), and had to
  be killed rather than left to potentially destabilize the machine. **A real `--smoke-test` run
  did not complete on this Mac** - treat any Mac attempt as "does data prep run," not "does
  training complete," until this project adds a lower-memory path (e.g. an 8-bit optimizer, or
  gradient checkpointing) - neither is wired up yet. The CUDA/ROCm path doesn't hit this because a
  dedicated 24GB GPU (like the RX 7900 XTX) doesn't share memory with the OS and other processes
  the way Mac unified memory does, and `bf16` halves the footprint versus fp32.

### Running it

```bash
# 1. Record your own reference clip if you haven't (needed as ref_audio for every training row)
uv run --with sounddevice --with soundfile --with numpy \
    python scripts/record_reference_voice.py --speaker-id shahriyor

# 2. Record a multi-sentence dataset (reuses that reference clip for every row, per the official
#    "strongly recommended: use the same ref_audio for all samples" guidance)
uv run --with sounddevice --with soundfile --with numpy \
    python scripts/record_tts_finetune_dataset.py --speaker-id shahriyor

# 3. Download the 1.7B base model (one-time, ~4.3GB)
uv run --project apps/ai-service python scripts/download_models.py download-tts-finetune-base

# 4. Smoke test - proves data prep + the pipeline wiring work. On a CUDA/ROCm machine this
#    should also complete training + save a checkpoint. On a <=24GB Mac, expect it to run out
#    of memory partway through sft_12hz.py (see "Device reality" above) - that's a real memory
#    ceiling, not a bug to chase.
uv run --project apps/ai-service --extra tts-finetune python scripts/train_tts_uzbek.py \
    --speaker-id shahriyor --init-model-path models/tts/qwen3-tts-1.7b-base --smoke-test

# 5. Real run, on a CUDA/ROCm machine
uv run --project apps/ai-service --extra tts-finetune python scripts/train_tts_uzbek.py \
    --speaker-id shahriyor --init-model-path models/tts/qwen3-tts-1.7b-base \
    --device cuda --epochs 10 --batch-size 4
```

`scripts/train_tts_uzbek.py` wraps both `prepare_data.py` (extracts 12Hz audio codes from your
wavs) and `sft_12hz.py` (the actual training loop) in sequence, using this project's dataset
layout (`data/processed_audio/<speaker-id>/train.jsonl`) and writing a `run_meta.json` (device,
dataset size, git commit, package versions) next to the checkpoints under
`models/tts/uzbek-voice/` for reproducibility.

### Known gaps

- **No training run has completed on this Mac** - it ran out of memory (see "Device reality"
  above). A real run needs a CUDA/ROCm GPU; this has not been attempted on the RX 7900 XTX PC yet.
- No `evaluate`/`export` command for fine-tuned checkpoints yet - listen to a checkpoint manually
  by loading it with `Qwen3TTSModel.from_pretrained()` and calling `generate_custom_voice()`.
- No automatic batch-size-reduction-and-retry on OOM, and no low-memory options (8-bit optimizer,
  gradient checkpointing) wired up - if a 24GB GPU also runs out of memory with the default
  `--batch-size`, the only lever right now is lowering `--batch-size` manually.
- `engines/tts.py`'s `generate_custom_voice()` path (for a fine-tuned checkpoint at
  `models/tts/uzbek-voice/`) has not been exercised end-to-end with a real trained checkpoint yet -
  only zero-shot cloning via the Base model has been verified serving real requests.
