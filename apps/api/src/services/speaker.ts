import fs from 'fs'
import path from 'path'
import { SpeakerProfile } from '@uzbek-local-voice-ai-ts-shared'

const speakersDir = path.resolve(process.cwd(), '../../data/speakers')

function ensureDir() {
  if (!fs.existsSync(speakersDir)) fs.mkdirSync(speakersDir, { recursive: true })
}

function speakerFilePath(speakerId: string) {
  return path.join(speakersDir, speakerId, 'speaker.json')
}

export const speakerService = {
  async list(): Promise<SpeakerProfile[]> {
    ensureDir()
    const speakers: SpeakerProfile[] = []
    for (const item of fs.readdirSync(speakersDir)) {
      const speakerPath = path.join(speakersDir, item)
      const metaPath = path.join(speakerPath, 'speaker.json')
      if (fs.existsSync(metaPath)) {
        speakers.push(JSON.parse(fs.readFileSync(metaPath, 'utf-8')))
      }
    }
    return speakers
  },
  async add(input: Partial<SpeakerProfile>): Promise<SpeakerProfile> {
    ensureDir()
    const speakerId = input.speakerId || input.displayName?.toLowerCase().replace(/\s+/g, '_') || 'speaker'
    const now = new Date().toISOString()
    const speaker: SpeakerProfile = {
      speakerId,
      displayName: input.displayName || 'New Speaker',
      language: input.language || 'uz',
      type: input.type || 'reference_or_finetuned',
      referenceAudio: input.referenceAudio || 'reference.wav',
      modelPath: input.modelPath || '',
      permission: input.permission || 'owned_by_user',
      createdAt: input.createdAt || now,
    }
    const dir = path.join(speakersDir, speakerId)
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(path.join(dir, 'speaker.json'), JSON.stringify(speaker, null, 2), 'utf-8')
    return speaker
  },
  async remove(speakerId: string) {
    const dir = path.join(speakersDir, speakerId)
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true, force: true })
    }
  },
}
