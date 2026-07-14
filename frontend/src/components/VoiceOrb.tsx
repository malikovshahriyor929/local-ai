import { useCallback, useEffect, useRef, useState } from 'react'
import { encodeWav } from '../lib/wav'
import { voiceChat, audioUrl, type VoiceChatResult } from '../lib/api'

type Status = 'idle' | 'opening' | 'recording' | 'processing' | 'speaking' | 'error'

const STATUS_LABEL: Record<Status, string> = {
  idle: "Gapirish uchun bosing",
  opening: 'Mikrofon ochilmoqda...',
  recording: 'Tinglayapman... (to‘xtatish uchun bosing)',
  processing: 'Qayta ishlanmoqda...',
  speaking: 'Javob berilmoqda...',
  error: 'Xatolik',
}

const STATUS_HUE: Record<Status, number> = {
  idle: 205,
  opening: 205,
  recording: 190,
  processing: 40,
  speaking: 140,
  error: 0,
}

interface Props {
  speakerId: string
  size?: number
  onResult?: (result: VoiceChatResult) => void
  disabled?: boolean
}

const SILENCE_AUTOSTOP_MS = 1600
const MIN_RECORDING_MS = 400

export default function VoiceOrb({ speakerId, size = 320, onResult, disabled }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number | null>(null)

  const audioCtxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const silentGainRef = useRef<GainNode | null>(null)

  const chunksRef = useRef<Float32Array[]>([])
  const sampleRateRef = useRef(48000)
  const recordingRef = useRef(false)
  const recordingStartedAtRef = useRef(0)
  const heardSpeechRef = useRef(false)
  const noiseFloorRef = useRef(0.015)
  const silenceMsRef = useRef(0)
  const lastFrameTsRef = useRef(0)
  const smoothVolRef = useRef(0)
  const statusRef = useRef<Status>('idle')

  const [status, setStatusState] = useState<Status>('idle')
  const [errorText, setErrorText] = useState('')

  const setStatus = useCallback((next: Status) => {
    statusRef.current = next
    setStatusState(next)
  }, [])

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }, [])

  const teardownAudio = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = null
    processorRef.current?.disconnect()
    processorRef.current = null
    silentGainRef.current?.disconnect()
    silentGainRef.current = null
    sourceRef.current?.disconnect()
    sourceRef.current = null
    analyserRef.current = null
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {})
      audioCtxRef.current = null
    }
    stopStream()
    recordingRef.current = false
  }, [stopStream])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const analyser = analyserRef.current
    if (!canvas) return

    const dpr = Math.max(1, Math.floor(window.devicePixelRatio || 1))
    const px = size
    if (canvas.width !== px * dpr || canvas.height !== px * dpr) {
      canvas.width = px * dpr
      canvas.height = px * dpr
    }
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let volume = 0
    if (analyser) {
      const freq = new Uint8Array(analyser.frequencyBinCount)
      const time = new Uint8Array(analyser.fftSize)
      analyser.getByteFrequencyData(freq)
      analyser.getByteTimeDomainData(time)
      let sumSq = 0
      for (let i = 0; i < time.length; i += 1) {
        const n = (time[i] - 128) / 128
        sumSq += n * n
      }
      const rms = Math.sqrt(sumSq / time.length)
      let freqSum = 0
      for (let i = 0; i < freq.length; i += 1) freqSum += freq[i]
      const freqVol = Math.min(1, ((freqSum / freq.length) / 155) * 2)
      const inputVol = Math.max(rms, freqVol * 0.35)
      const smooth = smoothVolRef.current
      volume = smoothVolRef.current = smooth + (inputVol - smooth) * (inputVol > smooth ? 0.35 : 0.12)

      // silence-based auto-stop while recording
      if (recordingRef.current) {
        const now = performance.now()
        const dt = Math.max(0, now - lastFrameTsRef.current)
        lastFrameTsRef.current = now

        if (!heardSpeechRef.current && inputVol < noiseFloorRef.current + 0.015) {
          noiseFloorRef.current = noiseFloorRef.current * 0.97 + inputVol * 0.03
        }
        const gateOn = Math.max(0.02, noiseFloorRef.current + 0.012)
        if (inputVol >= gateOn) {
          heardSpeechRef.current = true
          silenceMsRef.current = 0
        } else if (heardSpeechRef.current) {
          silenceMsRef.current += dt
        }

        const elapsed = now - recordingStartedAtRef.current
        if (heardSpeechRef.current && silenceMsRef.current >= SILENCE_AUTOSTOP_MS && elapsed >= MIN_RECORDING_MS) {
          // schedule stop outside the draw loop
          queueMicrotask(() => stopAndSendRef.current?.())
        }
      }
    }

    const hue = STATUS_HUE[statusRef.current]
    const cx = px / 2
    const cy = px / 2
    const t = performance.now() / 1000
    const baseR = px * 0.28
    const breathe = statusRef.current === 'processing' ? (Math.sin(t * 4) + 1) * 0.5 : (Math.sin(t * 1.2) + 1) * 0.5
    const r = baseR * (1 + 0.06 * breathe + volume * 0.4)

    ctx.save()
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, px, px)

    ctx.beginPath()
    ctx.arc(cx, cy, r + 10, 0, Math.PI * 2)
    ctx.strokeStyle = `hsla(${hue}, 90%, 60%, ${0.35 + volume * 0.35})`
    ctx.lineWidth = 10
    ctx.shadowColor = `hsla(${hue + 20}, 95%, 70%, ${0.55 + volume * 0.35})`
    ctx.shadowBlur = 8 + volume * 60
    ctx.stroke()
    ctx.shadowBlur = 0

    const body = ctx.createRadialGradient(cx, cy, r * 0.1, cx, cy, r)
    body.addColorStop(0, `hsla(${hue}, 95%, 22%, 1)`)
    body.addColorStop(0.55, `hsla(${hue + 20}, 90%, 30%, 1)`)
    body.addColorStop(1, `hsla(${hue + 40}, 85%, 18%, 1)`)
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.fillStyle = body
    ctx.fill()

    ctx.beginPath()
    ctx.lineWidth = 2
    ctx.strokeStyle = `hsla(${hue + 40}, 90%, 85%, 0.3)`
    ctx.arc(cx, cy, r - 1, 0, Math.PI * 2)
    ctx.stroke()
    ctx.restore()

    rafRef.current = requestAnimationFrame(draw)
  }, [size])

  const startListening = useCallback(async () => {
    if (disabled) return
    setErrorText('')
    setStatus('opening')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      streamRef.current = stream

      const AudioContextCtor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!AudioContextCtor) throw new Error('Bu brauzer Web Audio API ni qo‘llab-quvvatlamaydi')
      const audioCtx = new AudioContextCtor()
      if (audioCtx.state === 'suspended') await audioCtx.resume().catch(() => {})

      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 512
      analyser.smoothingTimeConstant = 0.8
      const source = audioCtx.createMediaStreamSource(stream)
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      const silentGain = audioCtx.createGain()
      silentGain.gain.value = 0

      chunksRef.current = []
      recordingRef.current = true
      recordingStartedAtRef.current = performance.now()
      heardSpeechRef.current = false
      silenceMsRef.current = 0
      noiseFloorRef.current = 0.015
      lastFrameTsRef.current = performance.now()

      processor.onaudioprocess = (event) => {
        if (!recordingRef.current) return
        chunksRef.current.push(new Float32Array(event.inputBuffer.getChannelData(0)))
      }

      source.connect(analyser)
      source.connect(processor)
      processor.connect(silentGain)
      silentGain.connect(audioCtx.destination)

      audioCtxRef.current = audioCtx
      analyserRef.current = analyser
      sourceRef.current = source
      processorRef.current = processor
      silentGainRef.current = silentGain
      sampleRateRef.current = audioCtx.sampleRate

      setStatus('recording')
      rafRef.current = requestAnimationFrame(draw)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Mikrofonga ruxsat berilmadi'
      setErrorText(message)
      setStatus('error')
      teardownAudio()
    }
  }, [disabled, draw, setStatus, teardownAudio])

  const stopAndSend = useCallback(async () => {
    if (!recordingRef.current) return
    recordingRef.current = false
    const blob = encodeWav(chunksRef.current, sampleRateRef.current)
    chunksRef.current = []
    teardownAudio()

    if (!heardSpeechRef.current || blob.size < 1000) {
      setStatus('idle')
      return
    }

    setStatus('processing')
    try {
      const result = await voiceChat(blob, speakerId)
      onResult?.(result)
      if (result.audio_path) {
        setStatus('speaking')
        const audio = new Audio(audioUrl(result.audio_path))
        audio.onended = () => setStatus('idle')
        audio.onerror = () => setStatus('idle')
        await audio.play().catch(() => setStatus('idle'))
      } else {
        setStatus('idle')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'So‘rov bajarilmadi'
      setErrorText(message)
      setStatus('error')
    }
  }, [onResult, setStatus, speakerId, teardownAudio])

  // draw() schedules auto-stop via this ref to avoid stale closures
  const stopAndSendRef = useRef<() => void>(() => {})
  useEffect(() => {
    stopAndSendRef.current = () => void stopAndSend()
  }, [stopAndSend])

  const handleClick = useCallback(() => {
    if (status === 'idle' || status === 'error') {
      void startListening()
    } else if (status === 'recording') {
      void stopAndSend()
    }
    // processing / opening / speaking: ignore clicks
  }, [startListening, status, stopAndSend])

  useEffect(() => {
    return () => teardownAudio()
  }, [teardownAudio])

  // idle-state gentle animation even without a stream
  useEffect(() => {
    if (status === 'idle' || status === 'processing' || status === 'speaking') {
      rafRef.current = requestAnimationFrame(draw)
      return () => {
        if (rafRef.current) cancelAnimationFrame(rafRef.current)
      }
    }
    return undefined
  }, [draw, status])

  const clickable = status === 'idle' || status === 'error' || status === 'recording'

  return (
    <div className="flex flex-col items-center gap-4">
      <button
        type="button"
        onClick={handleClick}
        disabled={!clickable || disabled}
        aria-label="Gapirish uchun bosing"
        className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:cursor-wait"
        style={{ width: size, height: size }}
      >
        <canvas ref={canvasRef} style={{ width: size, height: size, borderRadius: '9999px' }} aria-hidden />
      </button>
      <p className="text-slate-200 text-center max-w-sm min-h-[1.5rem]">
        {status === 'error' ? errorText || STATUS_LABEL.error : STATUS_LABEL[status]}
      </p>
    </div>
  )
}
