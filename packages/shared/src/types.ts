export interface SpeakerProfile {
  speakerId: string
  displayName: string
  language: string
  type: 'reference_or_finetuned' | 'prebuilt'
  referenceAudio: string
  modelPath: string
  permission: 'owned_by_user' | 'permitted'
  createdAt: string
}

export interface STTResult {
  text: string
  language?: string
  confidence?: number
  segments?: Array<{ start: number; end: number; text: string }>
}

export interface TTSResult {
  audioPath: string
  audioUrl: string
  durationMs?: number
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}
