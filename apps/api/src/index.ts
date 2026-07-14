import Fastify from 'fastify'
import cors from '@fastify/cors'
import multipart from '@fastify/multipart'
import staticPlugin from '@fastify/static'
import { fileURLToPath } from 'url'
import path from 'path'
import { config } from './config'
import { registerRoutes } from './routes'

const server = Fastify({ logger: true })

await server.register(cors, { origin: true })
await server.register(multipart)

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
await server.register(staticPlugin, {
  root: path.join(__dirname, '../../data/generated-audio'),
  prefix: '/audio/',
})

registerRoutes(server)

const port = Number(process.env.API_PORT || config.apiPort || 4000)
const host = process.env.API_HOST || config.apiHost || '0.0.0.0'

await server.listen({ port, host })
console.log(`API listening at http://${host}:${port}`)
