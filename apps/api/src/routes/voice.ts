import { FastifyInstance } from 'fastify'
import { sttService } from '../services/stt'
import { llmService } from '../services/llm'
import { ttsService } from '../services/tts'

export function voiceRoutes(server: FastifyInstance) {
  server.post('/voice-chat', async (request, reply) => {
    const file = await request.file()
    if (!file) return reply.status(400).send({ error: 'audio file is required' })

    const speakerId = (request.body as any)?.speakerId || 'female_assistant'
    const sttEngine = (request.body as any)?.sttEngine
    const ttsEngine = (request.body as any)?.ttsEngine
    const llmProvider = (request.body as any)?.llmProvider

    const audioPath = await sttService.saveUpload(file)
    const transcriptResult = await sttService.transcribeFile(audioPath, { sttEngine })
    const answerText = await llmService.chat([
      { role: 'user', content: transcriptResult.text },
    ], { provider: llmProvider })
    const ttsResult = await ttsService.synthesize(answerText, speakerId, { engine: ttsEngine })

    return {
      transcript: transcriptResult.text,
      answerText,
      audioUrl: ttsResult.audioUrl,
      speakerId,
    }
  })
}
