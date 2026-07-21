# Vendored: Qwen3-TTS official fine-tuning recipe

`dataset.py`, `prepare_data.py`, and `sft_12hz.py` are vendored from the official
[QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) repository
(`finetuning/` directory, fetched 2026-07-14), licensed Apache-2.0 (see each file's header).

**Why vendored instead of `pip install`ed**: this is a training *recipe* (argparse scripts +
a `Dataset` class), not a library API — the upstream repo doesn't publish it as an installable
package. Pinning the exact commit's version here avoids the pipeline silently changing under us
if upstream edits these scripts later.

**Local changes** (all additive CLI flags, upstream behavior is unchanged if you pass the old
hardcoded values explicitly): `prepare_data.py` and `sft_12hz.py` hardcoded `device="cuda:0"`,
`attn_implementation="flash_attention_2"`, and `torch_dtype=torch.bfloat16` / `mixed_precision="bf16"` -
all CUDA-only assumptions. These are now CLI flags that auto-pick a sane default per device
(`sdpa` attention everywhere except an explicit opt-in to flash-attention; `bf16` only when a
CUDA/ROCm GPU is detected, `fp32`/`no` mixed-precision otherwise). `sft_12hz.py` also fixes a real
upstream bug found by actually running it: `Accelerator(log_with="tensorboard")` without
`project_dir` raises `ValueError` on `accelerate>=1.0` ("Logging with tensorboard requires a
logging_dir") - added `project_dir=args.output_model_path`. See the diff against upstream for the
exact lines changed - the training loop, loss computation, and checkpoint format (embedding the
new speaker at codec vocabulary index 3000) are otherwise byte-for-byte identical to upstream.

**Reality check**: this fine-tunes a 0.6B-1.7B parameter transformer with custom internals
(speaker encoder, codec embeddings, sub-talker head) via `accelerate`. It is realistically a
CUDA/ROCm-only workload - see [`../../../docs/tts-finetuning.md`](../../../docs/tts-finetuning.md)
for what actually works on this project's Mac vs. the RX 7900 XTX PC.
