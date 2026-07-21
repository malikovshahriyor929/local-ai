#!/usr/bin/env python3
"""Fine-tune Qwen3-TTS for a single Uzbek speaker, using the vendored official recipe.

Wraps apps/ai-service/finetuning/{prepare_data,sft_12hz}.py (see that directory's
README.md for provenance) with this project's paths and device detection.

Two real steps run as subprocesses inside the apps/ai-service uv environment:
  1. prepare_data.py: extracts 12Hz audio codes for every training clip.
  2. sft_12hz.py: the actual fine-tuning loop (accelerate + AdamW), saving a
     checkpoint per epoch with the new speaker embedded at codec index 3000.

Usage (run via `uv run` in the ai-service project - this script itself imports torch):
    uv run --project apps/ai-service --extra tts-finetune python scripts/train_tts_uzbek.py \
        --speaker-id shahriyor --init-model-path models/tts/qwen3-tts-1.7b-base --smoke-test
    uv run --project apps/ai-service --extra tts-finetune python scripts/train_tts_uzbek.py \
        --speaker-id shahriyor --init-model-path models/tts/qwen3-tts-1.7b-base \
        --device cuda --epochs 10 --batch-size 4

IMPORTANT: --init-model-path must point at the 1.7B-Base checkpoint
(models/tts/qwen3-tts-1.7b-base, download with `python scripts/download_models.py
download-tts-finetune-base`), not the 0.6B-Base model used for zero-shot cloning
elsewhere in this project - see docs/tts-finetuning.md for why (a real tensor-shape
mismatch in the 0.6B checkpoint, not a bug in this script).

Reality check: this fine-tunes a 1.7B parameter transformer. --smoke-test proves
the pipeline runs and saves a checkpoint on any device (including CPU), but is not
a usable voice. A real run needs a CUDA/ROCm GPU - see docs/tts-finetuning.md.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINETUNE_DIR = ROOT / "apps" / "ai-service" / "finetuning"
# The 0.6B-Base model (used elsewhere for zero-shot cloning) has mismatched talker tensor
# shapes for this fine-tuning recipe (text_embedding 2048-dim vs codec_embedding 1024-dim) -
# see docs/tts-finetuning.md. Fine-tuning needs the 1.7B-Base checkpoint instead.
ZERO_SHOT_BASE_MODEL = ROOT / "models" / "tts" / "qwen3-tts-base"
DEFAULT_FINETUNE_BASE_MODEL = ROOT / "models" / "tts" / "qwen3-tts-1.7b-base"
DEFAULT_TOKENIZER = ZERO_SHOT_BASE_MODEL / "speech_tokenizer"


def count_jsonl_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def run_step(args: list[str], cwd: Path) -> None:
    print(f"\n$ (cwd={cwd}) {' '.join(args)}")
    result = subprocess.run(args, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(f"Step failed (exit {result.returncode}): {' '.join(args)}")


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--speaker-id", required=True)
    parser.add_argument("--init-model-path", default=str(DEFAULT_FINETUNE_BASE_MODEL))
    parser.add_argument("--tokenizer-path", default=str(DEFAULT_TOKENIZER))
    parser.add_argument("--output-model-path", default=None, help="Default: models/tts/uzbek-voice (matches TTS_MODEL_PATH in .env)")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu", "mps"], default="auto")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--attn-implementation", choices=["sdpa", "eager", "flash_attention_2"], default=None)
    parser.add_argument("--smoke-test", action="store_true", help="epochs=1, batch_size=1 - proves the pipeline runs, not a usable voice")
    args = parser.parse_args()

    dataset_dir = ROOT / "data" / "processed_audio" / args.speaker_id
    train_jsonl = dataset_dir / "train.jsonl"
    coded_jsonl = dataset_dir / "train_with_codes.jsonl"
    output_model_path = Path(args.output_model_path) if args.output_model_path else ROOT / "models" / "tts" / "uzbek-voice"

    if not train_jsonl.is_file():
        raise SystemExit(
            f"No dataset at {train_jsonl}. Record one first:\n"
            f"  uv run --with sounddevice --with soundfile --with numpy "
            f"python scripts/record_tts_finetune_dataset.py --speaker-id {args.speaker_id}"
        )
    n_rows = count_jsonl_rows(train_jsonl)
    if n_rows < 2:
        raise SystemExit(f"Only {n_rows} row(s) in {train_jsonl}. Record more sentences first.")

    if args.init_model_path == str(ZERO_SHOT_BASE_MODEL):
        raise SystemExit(
            "The 0.6B-Base model (qwen3-tts-base) has mismatched talker tensor shapes for this "
            "fine-tuning recipe and will crash mid-training - see docs/tts-finetuning.md. "
            f"Use the 1.7B-Base model instead: --init-model-path {DEFAULT_FINETUNE_BASE_MODEL}"
        )
    if not Path(args.init_model_path).is_dir():
        raise SystemExit(
            f"Model not found at {args.init_model_path}. Download it first:\n"
            f"  uv run --project apps/ai-service python scripts/download_models.py download-tts-finetune-base"
        )

    import torch  # local import: don't require torch just to print --help

    cuda_available = torch.cuda.is_available()  # true for ROCm-as-cuda too
    mps_available = torch.backends.mps.is_available()
    if args.device == "auto":
        device = "cuda" if cuda_available else ("mps" if mps_available else "cpu")
    else:
        device = args.device
    if device == "mps" and not args.smoke_test:
        print(
            "\nWARNING: sft_12hz.py has no MPS-specific handling and pokes at custom model "
            "internals (speaker_encoder, code_predictor, ...) that may not have MPS kernels. "
            "Expect this to be slow or to fail outright. Use --smoke-test to find out cheaply, "
            "or run the real job on a CUDA/ROCm machine.\n"
        )
    attn_impl = args.attn_implementation or "sdpa"

    epochs = 1 if args.smoke_test else args.epochs
    batch_size = min(args.batch_size, max(1, n_rows)) if args.smoke_test else args.batch_size

    print(f"Device: {device}  Dataset rows: {n_rows}  Epochs: {epochs}  Batch size: {batch_size}")

    prepare_device = "cuda:0" if device == "cuda" else device

    run_step(
        [
            "uv", "run", "--project", str(FINETUNE_DIR.parent), "--extra", "tts-finetune",
            "python", "prepare_data.py",
            "--device", prepare_device,
            "--tokenizer_model_path", args.tokenizer_path,
            "--input_jsonl", str(train_jsonl),
            "--output_jsonl", str(coded_jsonl),
        ],
        cwd=FINETUNE_DIR,
    )

    sft_args = [
        "uv", "run", "--project", str(FINETUNE_DIR.parent), "--extra", "tts-finetune",
        "python", "sft_12hz.py",
        "--init_model_path", args.init_model_path,
        "--output_model_path", str(output_model_path),
        "--train_jsonl", str(coded_jsonl),
        "--batch_size", str(batch_size),
        "--lr", str(args.lr),
        "--num_epochs", str(epochs),
        "--speaker_name", args.speaker_id,
        "--attn_implementation", attn_impl,
    ]
    if device == "cpu" or device == "mps":
        sft_args += ["--dtype", "float32", "--mixed_precision", "no"]

    run_meta = {
        "speaker_id": args.speaker_id,
        "dataset_rows": n_rows,
        "device": device,
        "epochs": epochs,
        "batch_size": batch_size,
        "smoke_test": args.smoke_test,
        "init_model_path": args.init_model_path,
        "output_model_path": str(output_model_path),
        "git_commit": git_commit(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    output_model_path.mkdir(parents=True, exist_ok=True)
    (output_model_path / "run_meta.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")

    run_step(sft_args, cwd=FINETUNE_DIR)

    print(f"\nDone. Checkpoints under: {output_model_path}")


if __name__ == "__main__":
    main()
