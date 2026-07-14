#!/usr/bin/env python3
"""Explicit, resumable Hugging Face downloader for this project's local models."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models.yaml"
MANIFEST = ROOT / "models/model-manifest.json"


def entries() -> dict[str, dict]:
    with CONFIG.open() as file:
        config = yaml.safe_load(file)
    return {"llm": config["llm"]["default"], "stt": config["stt"]["default"], "tts": config["tts"]["base"], "embeddings": config["embeddings"]["default"]}


def has_downloaded_payload(target: Path, entry: dict) -> bool:
    if entry.get("filename"):
        return target.is_file() and target.stat().st_size > 0
    if not target.is_dir():
        return False
    return any(
        path.is_file() and path.name != ".gitkeep" and ".cache" not in path.relative_to(target).parts
        for path in target.rglob("*")
    )


def disk_ok(entry: dict) -> bool:
    target = ROOT / entry["local_path"]
    free = shutil.disk_usage(target.parent).free / 1024**3
    needed = float(entry.get("expected_size_gb", 0)) + 1
    print(f"Bo‘sh joy: {free:.1f} GB; taxminan kerak: {needed:.1f} GB")
    return free >= needed


def manifest_update(name: str, entry: dict, status: str) -> None:
    payload = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"version": 1, "models": []}
    target = ROOT / entry["local_path"]
    record = {"name": name, "repository": entry["repository"], "revision": entry.get("revision", "main"), "filename": entry.get("filename"), "localPath": entry["local_path"], "license": entry.get("license", "See model repository"), "downloadDate": datetime.now(timezone.utc).isoformat(), "sizeBytes": target.stat().st_size if target.is_file() else sum(p.stat().st_size for p in target.rglob("*") if p.is_file()) if target.is_dir() else 0, "status": status}
    payload["models"] = [item for item in payload["models"] if item.get("name") != name] + [record]
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n")


def download(name: str, entry: dict) -> None:
    if os.getenv("OFFLINE_MODE", "false").lower() == "true":
        raise SystemExit("OFFLINE_MODE=true: model hubga ulanib bo‘lmaydi.")
    target = ROOT / entry["local_path"]
    exists = has_downloaded_payload(target, entry)
    if exists:
        print(f"{name}: mavjud, qayta yuklanmadi: {target}"); manifest_update(name, entry, "valid"); return
    if not disk_ok(entry): raise SystemExit("Diskda yetarli bo‘sh joy yo‘q.")
    answer = input(f"{name} ({entry['repository']}, taxminan {entry.get('expected_size_gb', '?')} GB) yuklansinmi? [y/N] ").strip().lower()
    if answer not in {"y", "yes", "ha"}: raise SystemExit("Yuklash bekor qilindi.")
    try:
        from huggingface_hub import hf_hub_download, snapshot_download
    except ImportError as exc: raise SystemExit("huggingface-hub o‘rnatilmagan. `pnpm setup` ni ishga tushiring.") from exc
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
    try:
        if entry.get("filename"):
            target.parent.mkdir(parents=True, exist_ok=True)
            downloaded = hf_hub_download(repo_id=entry["repository"], filename=entry["filename"], revision=entry.get("revision"), token=token, local_dir=str(target.parent), local_dir_use_symlinks=False, resume_download=True)
            if Path(downloaded).resolve() != target.resolve(): shutil.copy2(downloaded, target)
        else:
            snapshot_download(repo_id=entry["repository"], revision=entry.get("revision"), token=token, local_dir=str(target), local_dir_use_symlinks=False, resume_download=True)
    except Exception as exc:
        message = "Model yuklanmadi. Gated model bo‘lsa HF_TOKEN bilan ruxsat berilgan token kiriting."
        manifest_update(name, entry, "failed"); raise SystemExit(f"{message}\n{exc}") from exc
    manifest_update(name, entry, "valid")
    print(f"{name}: tayyor: {target}")


def verify(selected: list[str]) -> int:
    failed = 0
    for name, entry in entries().items():
        if selected and name not in selected: continue
        target = ROOT / entry["local_path"]
        valid = has_downloaded_payload(target, entry)
        print(f"{'OK' if valid else 'MISSING'}  {name}: {target}")
        manifest_update(name, entry, "valid" if valid else "missing")
        failed += not valid
    return int(failed)


parser = argparse.ArgumentParser()
parser.add_argument("command", choices=["list", "download-llm", "download-stt", "download-tts", "download-embeddings", "download-all", "verify"])
args = parser.parse_args()
models = entries()
if args.command == "list":
    for key, value in models.items(): print(f"{key}: {value['repository']} → {value['local_path']} ({value.get('expected_size_gb', '?')} GB)")
elif args.command == "verify": sys.exit(verify([]))
else:
    requested = list(models) if args.command == "download-all" else [args.command.removeprefix("download-")]
    for key in requested: download(key, models[key])
