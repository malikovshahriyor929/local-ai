#!/usr/bin/env python3
from __future__ import annotations
import os, platform, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
print(f"OS: {platform.system()} {platform.machine()}")
print("FFmpeg:", "topildi" if shutil.which("ffmpeg") else "topilmadi")
if not (ROOT / ".env").exists(): shutil.copy2(ROOT / ".env.example", ROOT / ".env"); print(".env yaratildi")
print("JavaScript va Python bog‘liqliklarini o‘rnating, so‘ng llama.cpp tayyorlanadi.")
subprocess.run(["pnpm", "install"], cwd=ROOT, check=True)
subprocess.run(["uv", "sync", "--project", "apps/ai-service", "--extra", "llm", "--extra", "stt", "--extra", "tts", "--extra", "dev"], cwd=ROOT, check=True)
subprocess.run(["uv", "run", "python", "scripts/setup_llama_cpp.py"], cwd=ROOT, check=True)
subprocess.run(["pnpm", "exec", "prisma", "generate", "--schema", "apps/web/prisma/schema.prisma"], cwd=ROOT, check=True)
answer = input("Katta model fayllarini hozir yuklashni boshlaysizmi? Har bir model alohida tasdiq so‘raydi. [y/N] ").strip().lower()
if answer in {"y", "yes", "ha"}:
    subprocess.run(["uv", "run", "--project", "apps/ai-service", "python", "scripts/download_models.py", "download-all"], cwd=ROOT, check=True)
else:
    print("Model yuklash o‘tkazib yuborildi: pnpm models:download download-llm")
