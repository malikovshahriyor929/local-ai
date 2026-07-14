import fs from 'fs'
import path from 'path'
import { pipeline } from 'stream/promises'
import { STTResult } from '@uzbek-local-voice-ai-ts-shared'
import { config } from '../config'

const uploadDir = path.resolve(process.cwd(), '../../data/tmp')
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true })

export const sttService = {
  async saveUpload(file: any): Promise<string> {
    const filename = `${Date.now()}-${file.filename}`
    const filepath = path.join(uploadDir, filename)
    const writable = fs.createWriteStream(filepath)
    await pipeline(file.file, writable)
    return filepath
  },
  async transcribeFile(filePath: string, options?: { sttEngine?: string }): Promise<STTResult> {
    const engine = options?.sttEngine || config.sttEngine
    if (engine === 'whisper-cpp') {
      return this.transcribeWithWhisperCpp(filePath)
    }
    return { text: 'Mock transcription not implemented', language: 'uz', confidence: 0.0 }
  },
  async transcribeWithWhisperCpp(filePath: string): Promise<STTResult> {
    const spawn = await import('child_process').then((m) => m.spawn)
    const args = [config.whisperCppPath, '--model', config.whisperCppModelPath, '--file', filePath, '--language', 'uz', '--output', 'json']
    const child = spawn('python3', args)
    let stdout = ''
    for await (const chunk of child.stdout) {
      stdout += chunk.toString()
    }
    await new Promise((resolve, reject) => {
      child.on('close', (code) => (code === 0 ? resolve(true) : reject(new Error(`whisper.cpp exited ${code}`))))
    })
    try {
      const parsed = JSON.parse(stdout)
      return {
        text: parsed.text || '',
        language: 'uz',
        confidence: parsed.avg_logprob || 0,
        segments: parsed.segments?.map((segment: any) => ({ start: segment.start, end: segment.end, text: segment.text })) || [],
      }
    } catch {
      return { text: stdout.trim(), language: 'uz' }
    }
  },
}
