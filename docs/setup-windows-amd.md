# Windows AMD (RX 7900 XTX)

Use Python 3.11+, Node 22+, pnpm, `uv`, CMake, a C++ compiler, Git and FFmpeg. Run `pnpm setup`; it builds a project-local llama.cpp with Vulkan at `tools/llama.cpp/build-vulkan`. It does not install CUDA, Ollama, or LM Studio.

After setup, run `pnpm models:download download-llm` and choose `y` at the size prompt. The default configuration targets Qwen 2.5 7B Q4_K_M. Vulkan support depends on the installed AMD driver; inspect `pnpm health` after starting the app.
