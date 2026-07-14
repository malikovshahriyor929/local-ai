import { FastifyInstance } from 'fastify'
import { settingsService } from '../services/settings'

export function settingsRoutes(server: FastifyInstance) {
  server.get('/settings', async () => settingsService.getAll())
  server.post('/settings', async (request) => {
    const body = request.body as Record<string, any>
    await settingsService.save(body)
    return { status: 'ok' }
  })
}
