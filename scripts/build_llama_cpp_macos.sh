#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; SRC="$ROOT/tools/llama.cpp/source"; BUILD="$ROOT/tools/llama.cpp/build-metal"
git clone --depth 1 https://github.com/ggerganov/llama.cpp.git "$SRC" 2>/dev/null || true
cmake -S "$SRC" -B "$BUILD" -DGGML_METAL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" --config Release -j
