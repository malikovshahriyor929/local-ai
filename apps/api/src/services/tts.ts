import fs from 'fs'
import path from 'path'
import { pipeline } from 'stream/promises'
import { TTSResult } from '@uzbek-local-voice-ai-ts-shared'
import { config } from '../config'

const uploadDir = path.resolve(process.cwd(), '../../data/tmp')
const audioOutDir = path.resolve(process.cwd(), '../../data/generated-audio')
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true })
if (!fs.existsSync(audioOutDir)) fs.mkdirSync(audioOutDir, { recursive: true })

async function saveUpload(file: any): Promise<string> {
  const filename = `${Date.now()}-${file.filename}`
  const filepath = path.join(uploadDir, filename)
  const writable = fs.createWriteStream(filepath)
  await pipeline(file.file, writable)
  return filepath
}

export const ttsService = {
  saveUpload,
  async synthesize(text: string, speakerId: string, options?: { engine?: string }): Promise<TTSResult> {
    const filename = `${Date.now()}-${speakerId}.wav`
    const outputPath = path.join(audioOutDir, filename)
    fs.writeFileSync(outputPath, `MOCK WAV for ${text}`)
    return { audioPath: outputPath, audioUrl: `/audio/${filename}` }
  },
  async transcribeAudio(filePath: string): Promise<string> {
    return 'Mock transcription result'
  },
  async chatAudio(transcript: string, body: any): Promise<string> {
    return `Mock assistant response to: ${transcript}`
  },
}
