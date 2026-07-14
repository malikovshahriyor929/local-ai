#!/usr/bin/env python3
from __future__ import annotations
import platform, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools/llama.cpp"
system = platform.system()
if system == "Windows": command = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/build_llama_cpp_windows.ps1")]
elif system == "Darwin": command = ["bash", str(ROOT / "scripts/build_llama_cpp_macos.sh")]
else: command = ["bash", str(ROOT / "scripts/build_llama_cpp_linux.sh")]
print(f"Project-local llama.cpp build: {system} → {TARGET}")
if not shutil.which(command[0]): raise SystemExit(f"Kerakli build shell topilmadi: {command[0]}")
sys.exit(subprocess.call(command, cwd=ROOT))
