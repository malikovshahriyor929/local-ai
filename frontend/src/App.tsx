import { useEffect, useState } from 'react'
import VoiceOrb from './components/VoiceOrb'
import {
  audioUrl,
  chat,
  getHealth,
  getSpeakers,
  speak,
  transcribeFile,
  type HealthStatus,
  type SpeakerProfile,
  type VoiceChatResult,
} from './lib/api'

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthError, setHealthError] = useState('')
  const [speakers, setSpeakers] = useState<SpeakerProfile[]>([])
  const [speakerId, setSpeakerId] = useState('female_assistant')

  const [transcript, setTranscript] = useState('')
  const [answer, setAnswer] = useState('')
  const [lastAudio, setLastAudio] = useState('')

  const [manualText, setManualText] = useState('')
  const [manualBusy, setManualBusy] = useState(false)
  const [manualFile, setManualFile] = useState<File | null>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err) => setHealthError(err instanceof Error ? err.message : 'Backend unreachable'))
    getSpeakers()
      .then((list) => {
        setSpeakers(list)
        if (list.length && !list.some((s) => s.speaker_id === speakerId)) {
          setSpeakerId(list[0].speaker_id)
        }
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleVoiceResult = (result: VoiceChatResult) => {
    setTranscript(result.transcript)
    setAnswer(result.answer_text)
    setLastAudio(result.audio_path)
  }

  const handleManualChat = async () => {
    if (!manualText.trim() || manualBusy) return
    setManualBusy(true)
    try {
      const chatRes = await chat(manualText)
      setAnswer(chatRes.answer)
      const speakRes = await speak(chatRes.answer, speakerId)
      setLastAudio(speakRes.audio_path)
      new Audio(audioUrl(speakRes.audio_path)).play().catch(() => {})
    } catch (err) {
      setAnswer(`Xatolik: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setManualBusy(false)
    }
  }

  const handleManualUpload = async () => {
    if (!manualFile || manualBusy) return
    setManualBusy(true)
    try {
      const result = await transcribeFile(manualFile, manualFile.name)
      setTranscript(result.transcript)
    } catch (err) {
      setTranscript(`Xatolik: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setManualBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-black text-white flex flex-col items-center px-6 py-10 gap-10">
      <header className="w-full max-w-3xl flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Uzbek Local Voice AI</h1>
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <span
            className={`h-2.5 w-2.5 rounded-full ${health ? 'bg-emerald-400' : healthError ? 'bg-red-500' : 'bg-slate-600'}`}
          />
          {health ? `${health.stt_engine} · ${health.llm_url}` : healthError || 'connecting...'}
        </div>
      </header>

      <section className="flex flex-col items-center gap-4">
        <select
          value={speakerId}
          onChange={(e) => setSpeakerId(e.target.value)}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-slate-200"
        >
          {speakers.length === 0 && <option value={speakerId}>{speakerId}</option>}
          {speakers.map((s) => (
            <option key={s.speaker_id} value={s.speaker_id}>
              {s.display_name}
            </option>
          ))}
        </select>

        <VoiceOrb speakerId={speakerId} size={300} onResult={handleVoiceResult} />
      </section>

      <section className="w-full max-w-2xl grid gap-4 sm:grid-cols-2">
        <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
          <h2 className="text-sm font-medium text-slate-400 mb-2">Siz aytdingiz</h2>
          <p className="text-slate-100 whitespace-pre-wrap min-h-[2.5rem]">{transcript || '—'}</p>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
          <h2 className="text-sm font-medium text-slate-400 mb-2">AI javobi</h2>
          <p className="text-slate-100 whitespace-pre-wrap min-h-[2.5rem]">{answer || '—'}</p>
          {lastAudio && (
            <audio className="mt-3 w-full" controls src={audioUrl(lastAudio)}>
              <track kind="captions" />
            </audio>
          )}
        </div>
      </section>

      <details className="w-full max-w-2xl bg-white/5 border border-white/10 rounded-2xl p-4">
        <summary className="cursor-pointer text-sm font-medium text-slate-300">
          Qo‘lda boshqarish (matn chat / fayl yuklash)
        </summary>
        <div className="mt-4 flex flex-col gap-4">
          <div>
            <label className="text-xs text-slate-400" htmlFor="manual-text">
              Matn yozib yuboring (LLM chat + TTS)
            </label>
            <div className="flex gap-2 mt-1">
              <input
                id="manual-text"
                type="text"
                value={manualText}
                onChange={(e) => setManualText(e.target.value)}
                placeholder="Salom, qandaysiz?"
                className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={handleManualChat}
                disabled={manualBusy || !manualText.trim()}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-sm font-medium"
              >
                Yuborish
              </button>
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-400" htmlFor="manual-file">
              Audio fayl yuklab transkript oling (STT)
            </label>
            <div className="flex gap-2 mt-1">
              <input
                id="manual-file"
                type="file"
                accept="audio/*"
                onChange={(e) => setManualFile(e.target.files?.[0] ?? null)}
                className="flex-1 text-sm text-slate-300"
              />
              <button
                type="button"
                onClick={handleManualUpload}
                disabled={manualBusy || !manualFile}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-sm font-medium"
              >
                Transkript
              </button>
            </div>
          </div>
        </div>
      </details>
    </div>
  )
}
