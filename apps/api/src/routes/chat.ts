import { FastifyInstance } from 'fastify'
import { llmService } from '../services/llm'

export function chatRoutes(server: FastifyInstance) {
  server.post('/chat', async (request) => {
    const body = request.body as any
    const text = body.text
    if (!text) return { error: 'Text is required' }
    const response = await llmService.chat([{ role: 'user', content: text }])
    return { answer: response }
  })
}
