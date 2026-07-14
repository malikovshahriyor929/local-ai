"""Single-speaker VITS fine-tuning on your recorded Uzbek dataset (Coqui TTS).

This trains a real VITS acoustic model from scratch on one speaker's
data/processed_audio/<speaker_id>/{wavs/,metadata.csv} - it does not fine-tune
OvozifyLabs/matcha-tts-uz-v1 itself (that checkpoint's own training recipe
isn't public), but VITS is what Coqui TTS actually knows how to train, and is
the standard approach for "give me a single-speaker TTS voice from my own
recordings" with this stack.

IMPORTANT - device reality: coqui-tts-trainer hardcodes `.cuda()` calls
throughout (no MPS support at all). On a Mac this can only run on CPU, which
is fine for a small --smoke-test run to prove the pipeline works end-to-end,
but is not a real training machine. On the Windows RX 7900 XTX box, ROCm
PyTorch exposes the GPU through the same `torch.cuda` API, so this script
should work there unmodified once ROCm-enabled PyTorch is installed - see
docs/windows-amd-setup.md / docs/setup-linux-rocm.md.

Install extras first:
    pip install -r requirements-dataset.txt
    pip install -r requirements-training.txt

Usage:
    # Smoke test on CPU/Mac - proves the pipeline works, not a usable voice
    python scripts/train_tts.py --speaker-id shahriyor --smoke-test

    # Real run on a CUDA/ROCm machine
    python scripts/train_tts.py --speaker-id shahriyor --device cuda --epochs 1000 --batch-size 16

    # Resume an interrupted run
    python scripts/train_tts.py --speaker-id shahriyor --resume-from ../models/tts/shahriyor/vits_uzbek-<timestamp>
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sentences_uz import DEFAULT_SENTENCES  # noqa: E402 - needs sys.path set up first


def detect_device(requested: str) -> tuple[str, str]:
    """Returns (device, note). device is what we actually use; note explains why."""
    import torch

    cuda_available = torch.cuda.is_available()  # True for real CUDA *and* ROCm-as-cuda
    mps_available = torch.backends.mps.is_available()

    if requested == "cuda":
        if not cuda_available:
            raise SystemExit("--device cuda requested but torch.cuda.is_available() is False.")
        return "cuda", "Using CUDA/ROCm GPU."

    if requested == "cpu":
        return "cpu", "CPU forced via --device cpu."

    # auto
    if cuda_available:
        return "cuda", "Auto-detected a CUDA/ROCm GPU."
    if mps_available:
        return (
            "cpu",
            "MPS is available but coqui-tts-trainer hardcodes `.cuda()` calls and has no MPS "
            "support - falling back to CPU. This will be slow; use --smoke-test for a quick "
            "pipeline check, and run real training on a CUDA/ROCm machine.",
        )
    return "cpu", "No GPU detected - running on CPU."


def count_dataset_rows(metadata_path: Path) -> int:
    if not metadata_path.exists():
        return 0
    with metadata_path.open("r", encoding="utf-8") as f:
        return sum(1 for row in csv.reader(f, delimiter="|") if row)


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=BACKEND_ROOT.parent, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def uzbek_pipe_formatter(root_path, meta_file, **kwargs):
    """Reads our project's 2-column `filename|text` metadata.csv (see DATASET_GUIDE.md and
    record_dataset.py) - Coqui's built-in `ljspeech` formatter requires 3 columns, which would
    force a format change across SpeakerManager.validate_dataset() and the recorder too."""
    speaker_name = kwargs.get("speaker_id") or "speaker"
    meta_path = Path(root_path) / meta_file
    items = []
    with meta_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            wav_file, _, text = line.partition("|")
            if not text:
                continue
            audio_file = Path(root_path) / "wavs" / wav_file
            items.append(
                {"text": text, "audio_file": str(audio_file), "speaker_name": speaker_name, "root_path": root_path}
            )
    return items


def package_versions() -> dict:
    versions = {}
    for pkg in ("torch", "torchaudio", "TTS", "trainer", "numpy"):
        try:
            module = __import__(pkg)
            versions[pkg] = getattr(module, "__version__", "unknown")
        except ImportError:
            versions[pkg] = "not installed"
    return versions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--speaker-id", required=True)
    parser.add_argument("--data-dir", default=None, help="Default: ../data/processed_audio/<speaker-id>")
    parser.add_argument("--output-dir", default=None, help="Default: ../models/tts/<speaker-id>")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--sample-rate", type=int, default=22050)
    parser.add_argument("--epochs", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--eval-split-size", type=float, default=0.1)
    parser.add_argument("--save-step", type=int, default=500)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Trim epochs/batch/eval to the minimum needed to prove the pipeline runs and saves "
        "a checkpoint. Not a usable voice.",
    )
    parser.add_argument("--resume-from", default=None, help="Path to a previous run dir to continue")
    args = parser.parse_args()

    speaker_id = args.speaker_id
    data_dir = Path(args.data_dir) if args.data_dir else BACKEND_ROOT / ".." / "data" / "processed_audio" / speaker_id
    data_dir = data_dir.resolve()
    output_dir = Path(args.output_dir) if args.output_dir else BACKEND_ROOT / ".." / "models" / "tts" / speaker_id
    output_dir = output_dir.resolve()

    metadata_path = data_dir / "metadata.csv"
    wavs_dir = data_dir / "wavs"
    if not metadata_path.exists() or not wavs_dir.exists():
        raise SystemExit(
            f"No dataset found at {data_dir}.\n"
            f"Record one first: python scripts/record_dataset.py --speaker-id {speaker_id}"
        )

    n_rows = count_dataset_rows(metadata_path)
    if n_rows < 3:
        raise SystemExit(
            f"Only {n_rows} recorded sentence(s) in {metadata_path}. Need at least a handful "
            "(ideally 5-10+ minutes of audio) before training is meaningful. "
            f"Record more with: python scripts/record_dataset.py --speaker-id {speaker_id}"
        )

    device, device_note = detect_device(args.device)
    print(f"Device: {device} ({device_note})")
    if device == "cpu" and not args.smoke_test:
        print(
            "\nWARNING: about to train on CPU without --smoke-test. This can take from hours to "
            "days depending on dataset size and is not recommended. Add --smoke-test for a quick "
            "pipeline check, or run on a CUDA/ROCm machine for a real training run.\n"
        )

    epochs = args.epochs
    batch_size = args.batch_size
    eval_split_size = args.eval_split_size
    run_eval = True
    save_step = args.save_step
    if args.smoke_test:
        epochs = 1
        batch_size = min(batch_size, 2, max(1, n_rows // 2))
        eval_split_size = max(0.34, 1 / n_rows) if n_rows >= 3 else 0.5
        run_eval = n_rows >= 4  # need at least 1 eval sample after the split
        save_step = 1
        print(f"Smoke test: epochs={epochs} batch_size={batch_size} eval_split_size={eval_split_size:.2f}")

    # Imports deferred until here so --help / dataset-missing errors above don't require
    # the (large) training extras to be installed.
    from TTS.tts.configs.shared_configs import BaseDatasetConfig
    from TTS.tts.configs.vits_config import VitsConfig
    from TTS.tts.datasets import load_tts_samples
    from TTS.tts.models.vits import Vits, VitsAudioConfig
    from TTS.tts.utils.text.tokenizer import TTSTokenizer
    from TTS.utils.audio import AudioProcessor
    from trainer import Trainer, TrainerArgs

    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_config = BaseDatasetConfig(
        formatter="uzbek_pipe",
        meta_file_train="metadata.csv",
        path=str(data_dir),
    )

    audio_config = VitsAudioConfig(
        sample_rate=args.sample_rate,
        win_length=1024,
        hop_length=256,
        num_mels=80,
        mel_fmin=0,
        mel_fmax=None,
    )

    config = VitsConfig(
        audio=audio_config,
        run_name=f"vits_uzbek_{speaker_id}",
        batch_size=batch_size,
        eval_batch_size=max(1, batch_size // 2) if batch_size > 1 else 1,
        num_loader_workers=0,
        num_eval_loader_workers=0,
        run_eval=run_eval,
        test_delay_epochs=-1,
        epochs=epochs,
        text_cleaner="basic_cleaners",  # lowercases + collapses whitespace, leaves oʻ/gʻ intact
        use_phonemes=False,
        compute_input_seq_cache=True,
        print_step=1,
        print_eval=True,
        mixed_precision=False,  # not reliably supported on CPU; enable manually for CUDA if desired
        output_path=str(output_dir),
        datasets=[dataset_config],
        save_step=save_step,
        save_best_after=0,
        # Coqui's default test_sentences are English and trigger "character not in vocabulary"
        # warnings against a Uzbek-only tokenizer built from this dataset. Use our own sentences
        # for the periodic generated validation samples instead.
        test_sentences=[[s] for s in DEFAULT_SENTENCES[:4]],
    )

    ap = AudioProcessor.init_from_config(config)
    tokenizer, config = TTSTokenizer.init_from_config(config)

    train_samples, eval_samples = load_tts_samples(
        dataset_config,
        eval_split=run_eval,
        eval_split_size=eval_split_size,
        formatter=uzbek_pipe_formatter,
    )
    print(f"Train samples: {len(train_samples)}  Eval samples: {len(eval_samples) if eval_samples else 0}")

    model = Vits(config, ap, tokenizer, speaker_manager=None)

    trainer_args = TrainerArgs(continue_path=args.resume_from) if args.resume_from else TrainerArgs()
    trainer = Trainer(
        trainer_args,
        config,
        str(output_dir),
        model=model,
        train_samples=train_samples,
        eval_samples=eval_samples,
    )

    run_meta = {
        "speaker_id": speaker_id,
        "data_dir": str(data_dir),
        "output_dir": str(output_dir),
        "device": device,
        "device_note": device_note,
        "smoke_test": args.smoke_test,
        "dataset_rows": n_rows,
        "config": {
            "epochs": epochs,
            "batch_size": batch_size,
            "sample_rate": args.sample_rate,
            "eval_split_size": eval_split_size,
        },
        "git_commit": git_commit(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": package_versions(),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")
    print(f"Run metadata: {output_dir / 'run_meta.json'}")

    trainer.fit()

    print(f"\nDone. Checkpoints under: {output_dir}")


if __name__ == "__main__":
    main()
