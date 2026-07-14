"""Interactive single-speaker TTS dataset recorder.

Reads one Uzbek sentence at a time, records your mic, lets you accept /
re-record / play back / skip, and writes wavs + metadata.csv in the exact
layout `SpeakerManager.validate_dataset()` and the Coqui training script
expect:

    data/processed_audio/<speaker_id>/wavs/000001.wav
    data/processed_audio/<speaker_id>/metadata.csv   (filename|transcript)

A consent record is required before the first recording and stored at
data/consent/<speaker_id>.json. Sessions are resumable: re-running the
script picks up after the last accepted line in metadata.csv.

Usage:
    python scripts/record_dataset.py --speaker-id shahriyor
    python scripts/record_dataset.py --speaker-id shahriyor --sentences-file my_sentences.txt
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
except ImportError as exc:  # pragma: no cover - exercised only when the extra isn't installed
    raise SystemExit(
        "Recording requires the 'dataset' extras: "
        "pip install -r requirements-dataset.txt"
    ) from exc

from sentences_uz import DEFAULT_SENTENCES

MIN_DURATION_S = 0.4
CLIP_PEAK_THRESHOLD = 0.99
QUIET_RMS_THRESHOLD = 0.003


@dataclass
class Clip:
    audio: np.ndarray
    sample_rate: int

    @property
    def duration_s(self) -> float:
        return len(self.audio) / self.sample_rate

    @property
    def peak(self) -> float:
        return float(np.max(np.abs(self.audio))) if len(self.audio) else 0.0

    @property
    def rms(self) -> float:
        return float(np.sqrt(np.mean(np.square(self.audio)))) if len(self.audio) else 0.0

    def warnings(self) -> list[str]:
        issues = []
        if self.duration_s < MIN_DURATION_S:
            issues.append(f"too short ({self.duration_s:.2f}s) - hold record longer")
        if self.peak >= CLIP_PEAK_THRESHOLD:
            issues.append(f"possible clipping (peak={self.peak:.3f}) - move back from the mic")
        if self.rms < QUIET_RMS_THRESHOLD and self.duration_s >= MIN_DURATION_S:
            issues.append(f"very quiet (rms={self.rms:.4f}) - speak louder / move closer")
        return issues


def record_clip(sample_rate: int) -> Clip:
    chunks: list[np.ndarray] = []
    recording = {"active": True}

    def callback(indata, frames, time_info, status):  # noqa: ANN001 - sounddevice callback signature
        if recording["active"]:
            chunks.append(indata.copy())

    stream = sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", callback=callback)
    stream.start()
    input()  # second Enter stops
    recording["active"] = False
    stream.stop()
    stream.close()

    audio = np.concatenate(chunks, axis=0).flatten() if chunks else np.zeros(0, dtype="float32")
    return Clip(audio=audio, sample_rate=sample_rate)


def load_sentences(path: str | None) -> list[str]:
    if not path:
        return list(DEFAULT_SENTENCES)
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def count_existing(metadata_path: Path) -> int:
    if not metadata_path.exists():
        return 0
    with metadata_path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def ensure_consent(consent_dir: Path, speaker_id: str) -> None:
    consent_path = consent_dir / f"{speaker_id}.json"
    if consent_path.exists():
        return

    print(f"\nNo consent record found for speaker '{speaker_id}'.")
    print("This dataset will be used to fine-tune a TTS voice from your recordings.")
    display_name = input("Display name for this speaker: ").strip() or speaker_id
    confirm = input("Do you consent to recording and using this voice for local TTS fine-tuning? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Consent not given. Aborting - no audio will be recorded.")
        raise SystemExit(1)

    consent_dir.mkdir(parents=True, exist_ok=True)
    consent = {
        "speaker_id": speaker_id,
        "display_name": display_name,
        "consent_given": True,
        "consent_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "intended_uses": ["personal_tts_finetuning", "local_inference"],
        "commercial_use_permission": False,
        "voice_cloning_permission": True,
        "revocation_contact": "the speaker (this is a locally recorded, self-owned dataset)",
        "dataset_version": 1,
        "recording_operator": display_name,
    }
    consent_path.write_text(json.dumps(consent, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Consent recorded at {consent_path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speaker-id", required=True)
    parser.add_argument("--sentences-file", default=None, help="Optional text file, one sentence per line")
    parser.add_argument("--sample-rate", type=int, default=22050)
    parser.add_argument("--output-root", default="../data/processed_audio", help="Relative to backend/")
    parser.add_argument("--consent-root", default="../data/consent", help="Relative to backend/")
    args = parser.parse_args()

    sentences = load_sentences(args.sentences_file)
    speaker_dir = Path(args.output_root) / args.speaker_id
    wavs_dir = speaker_dir / "wavs"
    metadata_path = speaker_dir / "metadata.csv"
    wavs_dir.mkdir(parents=True, exist_ok=True)

    ensure_consent(Path(args.consent_root), args.speaker_id)

    start_index = count_existing(metadata_path)
    if start_index >= len(sentences):
        print(f"All {len(sentences)} sentences already recorded for '{args.speaker_id}'.")
        print(f"Metadata: {metadata_path}")
        return

    if start_index:
        print(f"Resuming: {start_index}/{len(sentences)} already recorded.")

    total_duration = 0.0
    with metadata_path.open("a", encoding="utf-8", newline="") as metadata_file:
        writer = csv.writer(metadata_file, delimiter="|", quoting=csv.QUOTE_NONE, escapechar="\\")

        index = start_index
        while index < len(sentences):
            sentence = sentences[index]
            print(f"\n[{index + 1}/{len(sentences)}] {sentence}")
            print("Press Enter to start recording...")
            input()
            print("Recording... press Enter to stop.")
            clip = record_clip(args.sample_rate)

            issues = clip.warnings()
            print(f"Duration: {clip.duration_s:.2f}s  Peak: {clip.peak:.3f}  RMS: {clip.rms:.4f}")
            for issue in issues:
                print(f"  WARNING: {issue}")

            choice = input("[a]ccept  [r]e-record  [p]lay back  [s]kip  [q]uit: ").strip().lower()
            while choice == "p":
                sd.play(clip.audio, args.sample_rate)
                sd.wait()
                choice = input("[a]ccept  [r]e-record  [s]kip  [q]uit: ").strip().lower()

            if choice == "q":
                break
            if choice == "s":
                index += 1
                continue
            if choice == "r":
                continue  # re-record same sentence, don't advance index

            # accept (default on anything else, including bare Enter)
            filename = f"{index + 1:06d}.wav"
            sf.write(str(wavs_dir / filename), clip.audio, args.sample_rate, subtype="PCM_16")
            writer.writerow([filename, sentence])
            metadata_file.flush()
            total_duration += clip.duration_s
            index += 1

    recorded = count_existing(metadata_path)
    print(f"\nDone this session. {recorded}/{len(sentences)} sentences recorded for '{args.speaker_id}'.")
    print(f"New audio this session: {total_duration:.1f}s (~{total_duration / 60:.1f} min)")
    print(f"Metadata: {metadata_path}")
    print(f"Wavs:     {wavs_dir}")
    if recorded < len(sentences):
        print("Re-run this command to resume where you left off.")
    else:
        print("Next: python scripts/train_tts.py --speaker-id " + args.speaker_id)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Progress up to the last accepted sentence was saved.")
        sys.exit(130)
