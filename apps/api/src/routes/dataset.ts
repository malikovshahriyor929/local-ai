import { FastifyInstance } from 'fastify'

export function datasetRoutes(server: FastifyInstance) {
  server.post('/dataset/import', async () => ({ status: 'not implemented' }))
  server.post('/dataset/validate', async () => ({ status: 'not implemented' }))
  server.post('/dataset/split-audio', async () => ({ status: 'not implemented' }))
  server.post('/dataset/normalize-audio', async () => ({ status: 'not implemented' }))
  server.post('/dataset/generate-metadata', async () => ({ status: 'not implemented' }))
}
