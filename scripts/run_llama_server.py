#!/usr/bin/env python3
"""Optional project-managed llama-server fallback; never uses a global binary."""
from __future__ import annotations
import os, platform, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
suffix = ".exe" if platform.system() == "Windows" else ""
matches = list((ROOT / "tools/llama.cpp").glob(f"build*/bin/llama-server{suffix}"))
if not matches: raise SystemExit("Project-local llama-server topilmadi. Avval `uv run python scripts/setup_llama_cpp.py` ni bajaring.")
model = Path(os.getenv("LLM_MODEL_PATH", "models/llm/model.gguf")); model = model if model.is_absolute() else ROOT / model
if not model.is_file(): raise SystemExit(f"GGUF model topilmadi: {model}")
subprocess.run([str(matches[0]), "-m", str(model), "-c", os.getenv("LLM_CONTEXT_SIZE", "8192"), "-ngl", os.getenv("LLM_GPU_LAYERS", "-1")], check=True)
