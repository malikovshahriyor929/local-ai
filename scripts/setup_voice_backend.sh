#!/bin/sh
# One-time setup for the Uzbek voice backend that VoicePilot Mac starts.
# Installs the Python environment and downloads only the speech models
# VoicePilot needs (STT + Uzbek voice), not the chat LLM.
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "VoicePilot voice backend setup"
echo "Project: $ROOT_DIR"
echo

if ! command -v uv >/dev/null 2>&1; then
  echo "The 'uv' tool is required but was not found." >&2
  echo "Install it with:  brew install uv" >&2
  exit 1
fi
echo "uv: $(command -v uv)"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "WARNING: ffmpeg was not found. Speech recognition needs it." >&2
  echo "Install it with:  brew install ffmpeg" >&2
fi

echo
echo "Step 1/3: installing the Python environment (this takes a few minutes)..."
uv sync --project apps/ai-service --extra stt --extra tts

echo
echo "Step 2/3: downloading speech models (about 0.7 GB)..."
uv run --project apps/ai-service python scripts/download_models.py download-stt
uv run --project apps/ai-service python scripts/download_models.py download-tts-mms

echo
echo "Step 3/3: verifying..."
uv run --project apps/ai-service python scripts/download_models.py verify || true

echo
echo "Done. VoicePilot Mac starts this backend automatically."
echo "Settings -> Speech recognition -> 'Voice service project folder' must be:"
echo "  $ROOT_DIR"
