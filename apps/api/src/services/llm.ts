import fetch from 'node-fetch'
import { ChatMessage } from '@uzbek-local-voice-ai-ts-shared'
import { config } from '../config'

export const llmService = {
  async chat(messages: ChatMessage[]): Promise<string> {
    const payload = {
      model: config.llmModel,
      messages: [
        { role: 'system', content: 'You are a helpful Uzbek voice assistant. Reply naturally in Uzbek Latin script.' },
        ...messages,
      ],
      temperature: 0.7,
    }
    const response = await fetch(`${config.llmBaseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      throw new Error(`LLM request failed: ${response.statusText}`)
    }
    const data = await response.json()
    return data.choices?.[0]?.message?.content || ''
  },
}
