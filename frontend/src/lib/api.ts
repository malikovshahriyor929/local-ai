export const API_BASE: string =
  (import.meta as unknown as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ??
  'http://localhost:8000'

export interface SpeakerProfile {
  speaker_id: string
  display_name: string
  type: string
  language: string
  reference_audio: string
  model_path: string
  permission: string
}

export interface HealthStatus {
  status: string
  stt_engine: string
  llm_url: string
}

export interface VoiceChatResult {
  transcript: string
  answer_text: string
  audio_path: string
  speaker_id: string
}

export interface SttResult {
  transcript: string
}

export interface SpeakResult {
  audio_path: string
  speaker_id: string
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body?.detail ?? detail
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

export function audioUrl(audioPath: string): string {
  return `${API_BASE}${audioPath}`
}

export async function getHealth(): Promise<HealthStatus> {
  return asJson(await fetch(`${API_BASE}/health`))
}

export async function getSpeakers(): Promise<SpeakerProfile[]> {
  return asJson(await fetch(`${API_BASE}/speakers`))
}

export async function transcribeFile(file: Blob, filename = 'speech.wav'): Promise<SttResult> {
  const form = new FormData()
  form.append('file', file, filename)
  return asJson(await fetch(`${API_BASE}/stt/file`, { method: 'POST', body: form }))
}

export async function chat(text: string): Promise<{ answer: string }> {
  return asJson(
    await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
  )
}

export async function speak(text: string, speakerId: string): Promise<SpeakResult> {
  return asJson(
    await fetch(`${API_BASE}/speak`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, speaker_id: speakerId }),
    })
  )
}

export async function voiceChat(file: Blob, speakerId: string, filename = 'speech.wav'): Promise<VoiceChatResult> {
  const form = new FormData()
  form.append('file', file, filename)
  const url = `${API_BASE}/voice-chat?speaker_id=${encodeURIComponent(speakerId)}`
  return asJson(await fetch(url, { method: 'POST', body: form }))
}
