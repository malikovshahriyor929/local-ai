import { FastifyInstance } from 'fastify'
import { ttsService } from '../services/tts'

export function ttsRoutes(server: FastifyInstance) {
  server.post('/tts', async (request, reply) => {
    const body = request.body as any
    const result = await ttsService.synthesize(body.text, body.speakerId)
    return result
  })
}
