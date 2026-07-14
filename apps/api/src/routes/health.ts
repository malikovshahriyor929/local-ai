import { FastifyInstance } from 'fastify'
import { config } from '../config'

export function healthRoutes(server: FastifyInstance) {
  server.get('/health', async () => ({
    status: 'ok',
    sttEngine: config.sttEngine,
    llmProvider: config.llmProvider,
  }))
}
