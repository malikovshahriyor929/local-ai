from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

import psutil


def _command_version(command: list[str]) -> str | None:
    if not shutil.which(command[0]):
        return None
    try:
        return subprocess.check_output(command, stderr=subprocess.STDOUT, text=True, timeout=3).splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        return "available"


def detect_system() -> dict[str, object]:
    system = platform.system()
    metal = system == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}
    vulkan = bool(shutil.which("vulkaninfo") or shutil.which("vulkaninfoSDK"))
    rocm = bool(shutil.which("rocminfo"))
    gpu_name = "Aniqlanmadi"
    vram_mb = None
    if shutil.which("nvidia-smi"):
        try:
            row = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], text=True, timeout=3).splitlines()[0]
            gpu_name, raw_vram = (item.strip() for item in row.split(",", 1))
            vram_mb = int(raw_vram)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    elif system == "Darwin":
        gpu_name = "Apple Silicon (unified memory)" if metal else "Apple GPU"
    elif rocm:
        gpu_name = "AMD GPU (ROCm)"
    elif vulkan:
        gpu_name = "Vulkan GPU"
    backend = "metal" if metal else "vulkan" if vulkan else "rocm" if rocm else "cpu"
    return {
        "os": f"{system} {platform.release()}", "architecture": platform.machine(), "cpu": platform.processor() or "Unknown CPU",
        "cpuCores": psutil.cpu_count(logical=False) or psutil.cpu_count(), "ramTotalMb": round(psutil.virtual_memory().total / 1024 / 1024),
        "ramUsedMb": round(psutil.virtual_memory().used / 1024 / 1024), "gpu": gpu_name, "vramMb": vram_mb,
        "vulkan": vulkan, "rocm": rocm, "metal": metal, "selectedBackend": backend,
        "ffmpeg": _command_version(["ffmpeg", "-version"]),
    }
