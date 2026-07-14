import { FastifyInstance } from 'fastify'
import { sttService } from '../services/stt'

export function sttRoutes(server: FastifyInstance) {
  server.post('/stt/file', async (request, reply) => {
    const data = await request.file()
    if (!data) return reply.status(400).send({ error: 'File is required' })
    const tempPath = await sttService.saveUpload(data)
    const result = await sttService.transcribeFile(tempPath)
    return result
  })

  server.post('/stt/mic-chunk', async (request) => {
    const data = await request.file()
    if (!data) return { error: 'File is required' }
    const tempPath = await sttService.saveUpload(data)
    const result = await sttService.transcribeFile(tempPath)
    return result
  })
}
