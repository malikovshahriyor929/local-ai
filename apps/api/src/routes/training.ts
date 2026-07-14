import { FastifyInstance } from 'fastify'

export function trainingRoutes(server: FastifyInstance) {
  server.post('/training/start', async () => ({ status: 'starting', message: 'Training endpoint not yet implemented' }))
  server.get('/training/status', async () => ({ status: 'idle' }))
  server.post('/training/stop', async () => ({ status: 'stopped' }))
}
