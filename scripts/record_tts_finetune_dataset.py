#!/usr/bin/env python3
"""Record a multi-sentence Uzbek dataset for Qwen3-TTS single-speaker fine-tuning.

Produces the exact JSONL format the vendored official recipe
(apps/ai-service/finetuning/{prepare_data,sft_12hz}.py) expects: one line per
sample with "audio", "text", and "ref_audio" fields. Per the official
fine-tuning README, the SAME ref_audio is used for every row - this reuses
the single clip you already recorded with record_reference_voice.py.

Audio is saved at exactly 24000 Hz mono (apps/ai-service/finetuning/dataset.py
hard-asserts `sr == 24000`, no tolerance).

Run with uv (ephemeral deps, no need to touch apps/ai-service's own
pyproject.toml for a one-off recording utility):

    uv run --with sounddevice --with soundfile --with numpy \
        python scripts/record_tts_finetune_dataset.py --speaker-id shahriyor
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing recording deps. Run with:\n"
        "  uv run --with sounddevice --with soundfile --with numpy "
        "python scripts/record_tts_finetune_dataset.py --speaker-id shahriyor"
    ) from exc

from sentences_uz import DEFAULT_SENTENCES

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_SAMPLE_RATE = 24000
MIN_DURATION_S = 0.6
CLIP_PEAK_THRESHOLD = 0.99
QUIET_RMS_THRESHOLD = 0.003


def record_clip(sample_rate: int) -> np.ndarray:
    chunks: list[np.ndarray] = []
    state = {"active": True}

    def callback(indata, frames, time_info, status):  # noqa: ANN001
        if state["active"]:
            chunks.append(indata.copy())

    stream = sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", callback=callback)
    stream.start()
    input()
    state["active"] = False
    stream.stop()
    stream.close()
    return np.concatenate(chunks, axis=0).flatten() if chunks else np.zeros(0, dtype="float32")


def diagnose(audio: np.ndarray, sample_rate: int) -> list[str]:
    duration = len(audio) / sample_rate
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0
    issues = []
    if duration < MIN_DURATION_S:
        issues.append(f"too short ({duration:.2f}s)")
    if peak >= CLIP_PEAK_THRESHOLD:
        issues.append(f"possible clipping (peak={peak:.3f})")
    if rms < QUIET_RMS_THRESHOLD and duration >= MIN_DURATION_S:
        issues.append(f"very quiet (rms={rms:.4f})")
    print(f"Duration: {duration:.2f}s  Peak: {peak:.3f}  RMS: {rms:.4f}")
    return issues


def load_sentences(path: str | None) -> list[str]:
    if not path:
        return list(DEFAULT_SENTENCES)
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def count_existing(jsonl_path: Path) -> int:
    if not jsonl_path.exists():
        return 0
    with jsonl_path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--speaker-id", required=True)
    parser.add_argument("--sentences-file", default=None, help="Optional text file, one sentence per line")
    args = parser.parse_args()

    speaker_dir = ROOT / "data" / "speakers" / args.speaker_id
    speaker_json = speaker_dir / "speaker.json"
    if not speaker_json.is_file():
        raise SystemExit(f"No speaker profile at {speaker_json}. Create one first.")
    profile = json.loads(speaker_json.read_text(encoding="utf-8"))
    ref_audio = speaker_dir / (profile.get("reference_audio") or "reference.wav")
    if not ref_audio.is_file():
        raise SystemExit(
            f"No reference clip at {ref_audio}. Record it first (needed as ref_audio for every "
            f"row per the official fine-tuning recipe):\n"
            f"  uv run --with sounddevice --with soundfile --with numpy "
            f"python scripts/record_reference_voice.py --speaker-id {args.speaker_id}"
        )

    dataset_dir = ROOT / "data" / "processed_audio" / args.speaker_id
    wavs_dir = dataset_dir / "wavs"
    jsonl_path = dataset_dir / "train.jsonl"
    wavs_dir.mkdir(parents=True, exist_ok=True)

    sentences = load_sentences(args.sentences_file)
    start_index = count_existing(jsonl_path)
    if start_index >= len(sentences):
        print(f"All {len(sentences)} sentences already recorded for '{args.speaker_id}'.")
        print(f"JSONL: {jsonl_path}")
        return
    if start_index:
        print(f"Resuming: {start_index}/{len(sentences)} already recorded.")

    print(f"Reference audio (used for every row): {ref_audio}")
    total_duration = 0.0

    with jsonl_path.open("a", encoding="utf-8") as jsonl_file:
        index = start_index
        while index < len(sentences):
            sentence = sentences[index]
            print(f"\n[{index + 1}/{len(sentences)}] {sentence}")
            print("Press Enter to start recording...")
            input()
            print("Recording... press Enter to stop.")
            audio = record_clip(REQUIRED_SAMPLE_RATE)

            issues = diagnose(audio, REQUIRED_SAMPLE_RATE)
            for issue in issues:
                print(f"  WARNING: {issue}")

            choice = input("[a]ccept  [r]e-record  [p]lay back  [s]kip  [q]uit: ").strip().lower()
            while choice == "p":
                sd.play(audio, REQUIRED_SAMPLE_RATE)
                sd.wait()
                choice = input("[a]ccept  [r]e-record  [s]kip  [q]uit: ").strip().lower()

            if choice == "q":
                break
            if choice == "s":
                index += 1
                continue
            if choice == "r":
                continue

            filename = f"{index + 1:06d}.wav"
            wav_path = wavs_dir / filename
            sf.write(str(wav_path), audio, REQUIRED_SAMPLE_RATE, subtype="PCM_16")
            jsonl_file.write(
                json.dumps(
                    {"audio": str(wav_path), "text": sentence, "ref_audio": str(ref_audio)},
                    ensure_ascii=False,
                )
                + "\n"
            )
            jsonl_file.flush()
            total_duration += len(audio) / REQUIRED_SAMPLE_RATE
            index += 1

    recorded = count_existing(jsonl_path)
    print(f"\nDone this session. {recorded}/{len(sentences)} sentences recorded for '{args.speaker_id}'.")
    print(f"New audio this session: {total_duration:.1f}s (~{total_duration / 60:.1f} min)")
    print(f"JSONL: {jsonl_path}")
    if recorded < len(sentences):
        print("Re-run this command to resume where you left off.")
    else:
        print("Next: python scripts/train_tts_uzbek.py --speaker-id " + args.speaker_id)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Progress up to the last accepted sentence was saved.")
