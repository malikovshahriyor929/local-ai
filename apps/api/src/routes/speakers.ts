import { FastifyInstance } from 'fastify'
import { speakerService } from '../services/speaker'

export function speakerRoutes(server: FastifyInstance) {
  server.get('/speakers', async () => speakerService.list())
  server.post('/speakers', async (request, reply) => {
    const body = request.body as any
    const speaker = await speakerService.add(body)
    reply.code(201)
    return speaker
  })
  server.delete('/speakers/:speakerId', async (request, reply) => {
    const { speakerId } = request.params as any
    await speakerService.remove(speakerId)
    reply.code(204).send()
  })
}
