#!/usr/bin/env python3
"""Record a short reference voice clip for Qwen3-TTS zero-shot cloning.

The Qwen3-TTS Base model (models/tts/qwen3-tts-base) clones a voice from a
single clean 3-10 second reference clip - it does not need a trained
checkpoint. This script records that one clip via your mic and saves it
where app/engines/tts.py's LocalTTSEngine._reference_audio() expects it:

    data/speakers/<speaker-id>/<reference_audio field from speaker.json>

Run with uv (no need to add sounddevice/soundfile to the project's own
pyproject.toml for a one-off recording utility):

    uv run --with sounddevice --with soundfile --with numpy \
        python scripts/record_reference_voice.py --speaker-id shahriyor
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
        "python scripts/record_reference_voice.py --speaker-id shahriyor"
    ) from exc

ROOT = Path(__file__).resolve().parent.parent
MIN_DURATION_S = 2.0
MAX_RECOMMENDED_S = 12.0
CLIP_PEAK_THRESHOLD = 0.99
QUIET_RMS_THRESHOLD = 0.003

SUGGESTED_TEXT = (
    "Assalomu alaykum, mening ismim Shahriyor. Men mahalliy sun'iy intellekt "
    "yordamchisi uchun o'z ovozimni yozib olyapman. Bugun ob-havo juda yaxshi."
)


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
        issues.append(f"too short ({duration:.1f}s) - aim for {MIN_DURATION_S:.0f}-{MAX_RECOMMENDED_S:.0f}s")
    if duration > MAX_RECOMMENDED_S + 5:
        issues.append(f"quite long ({duration:.1f}s) - a focused {MAX_RECOMMENDED_S:.0f}s clip clones better")
    if peak >= CLIP_PEAK_THRESHOLD:
        issues.append(f"possible clipping (peak={peak:.3f}) - move back from the mic")
    if rms < QUIET_RMS_THRESHOLD and duration >= MIN_DURATION_S:
        issues.append(f"very quiet (rms={rms:.4f}) - speak louder / move closer")
    print(f"Duration: {duration:.2f}s  Peak: {peak:.3f}  RMS: {rms:.4f}")
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--speaker-id", default="shahriyor")
    parser.add_argument("--sample-rate", type=int, default=24000)
    args = parser.parse_args()

    speaker_dir = ROOT / "data" / "speakers" / args.speaker_id
    speaker_json = speaker_dir / "speaker.json"
    if not speaker_json.is_file():
        raise SystemExit(
            f"No speaker profile at {speaker_json}. Create it first via the API "
            f"(POST /speakers/add) or by hand before recording a reference clip."
        )
    profile = json.loads(speaker_json.read_text(encoding="utf-8"))
    reference_name = profile.get("reference_audio") or "reference.wav"
    output_path = speaker_dir / reference_name

    print(f"Recording a reference voice clip for speaker '{args.speaker_id}' ({profile.get('display_name')}).")
    print(f"Will be saved to: {output_path}")
    print(
        "\nThis clip will be used to clone this voice with Qwen3-TTS locally. Only record your "
        "own voice, or a voice you have explicit permission to use - this project does not send "
        "audio anywhere off this machine, but the resulting clone can say anything you type.\n"
    )
    print("Suggested text to read (any natural Uzbek speech works, 3-10 seconds):")
    print(f"  \"{SUGGESTED_TEXT}\"\n")

    while True:
        input("Press Enter to start recording, then Enter again to stop...")
        print("Recording... press Enter to stop.")
        audio = record_clip(args.sample_rate)
        issues = diagnose(audio, args.sample_rate)
        for issue in issues:
            print(f"  WARNING: {issue}")

        choice = input("[a]ccept  [r]e-record  [p]lay back  [q]uit: ").strip().lower()
        while choice == "p":
            sd.play(audio, args.sample_rate)
            sd.wait()
            choice = input("[a]ccept  [r]e-record  [q]uit: ").strip().lower()

        if choice == "q":
            print("Cancelled - no file written.")
            return
        if choice == "r":
            continue

        speaker_dir.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, args.sample_rate, subtype="PCM_16")
        print(f"\nSaved: {output_path}")
        print(
            f"Next: POST http://127.0.0.1:8001/api/tts/synthesize "
            f'{{"text": "...", "speakerId": "{args.speaker_id}"}}'
        )
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted - no file written.")
