$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot; $Source = Join-Path $Root "tools/llama.cpp/source"; $Build = Join-Path $Root "tools/llama.cpp/build-vulkan"
if (!(Test-Path $Source)) { git clone --depth 1 https://github.com/ggerganov/llama.cpp.git $Source }
cmake -S $Source -B $Build -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release
cmake --build $Build --config Release --parallel
