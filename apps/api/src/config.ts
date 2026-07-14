import dotenv from 'dotenv'
import fs from 'fs'
import path from 'path'

function findEnv(startDir: string): string {
  let current = startDir
  while (true) {
    const candidate = path.join(current, '.env')
    if (fs.existsSync(candidate)) return candidate
    const parent = path.dirname(current)
    if (parent === current) break
    current = parent
  }
  return path.resolve(startDir, '.env')
}

dotenv.config({ path: findEnv(process.cwd()) })

export const config = {
  apiPort: process.env.API_PORT ? Number(process.env.API_PORT) : 4000,
  apiHost: process.env.API_HOST || '0.0.0.0',
  llmProvider: process.env.LLM_PROVIDER || 'openai-compatible',
  llmBaseUrl: process.env.LLM_BASE_URL || 'http://localhost:11434',
  llmModel: process.env.LLM_MODEL || 'gpt-4o-mini',
  sttEngine: process.env.STT_ENGINE || 'whisper-cpp',
  whisperCppPath: process.env.WHISPER_CPP_PATH || '/usr/local/bin/whisper.cpp',
  whisperCppModelPath: process.env.WHISPER_CPP_MODEL_PATH || './data/models/stt/ggml-small.bin',
  ttsEngine: process.env.TTS_ENGINE || 'mock',
  ttsServiceUrl: process.env.TTS_SERVICE_URL || 'http://localhost:5001',
  defaultSpeaker: process.env.DEFAULT_SPEAKER || 'female_assistant',
  databasePath: process.env.DATABASE_PATH || './data/app.db',
  audioOutputDir: process.env.AUDIO_OUTPUT_DIR || './data/generated-audio',
}
