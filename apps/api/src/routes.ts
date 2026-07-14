import { FastifyInstance } from 'fastify'
import { healthRoutes } from './routes/health'
import { speakerRoutes } from './routes/speakers'
import { sttRoutes } from './routes/stt'
import { chatRoutes } from './routes/chat'
import { ttsRoutes } from './routes/tts'
import { voiceRoutes } from './routes/voice'
import { datasetRoutes } from './routes/dataset'
import { trainingRoutes } from './routes/training'
import { settingsRoutes } from './routes/settings'

export function registerRoutes(server: FastifyInstance) {
  healthRoutes(server)
  speakerRoutes(server)
  sttRoutes(server)
  chatRoutes(server)
  ttsRoutes(server)
  voiceRoutes(server)
  settingsRoutes(server)
  datasetRoutes(server)
  trainingRoutes(server)
}
