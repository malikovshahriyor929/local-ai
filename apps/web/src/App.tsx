import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:4000'

type Speaker = { speakerId: string; displayName: string }

function App() {
  const [status, setStatus] = useState<any>(null)
  const [speakers, setSpeakers] = useState<Speaker[]>([])
  const [selectedSpeaker, setSelectedSpeaker] = useState('female_assistant')
  const [file, setFile] = useState<File | null>(null)
  const [transcript, setTranscript] = useState('')
  const [answer, setAnswer] = useState('')
  const [audioUrl, setAudioUrl] = useState('')

  useEffect(() => {
    fetch(`${API_BASE}/health`).then((res) => res.json()).then(setStatus)
    fetch(`${API_BASE}/speakers`).then((res) => res.json()).then(setSpeakers)
  }, [])

  const handleUpload = async () => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API_BASE}/stt/file`, { method: 'POST', body: form })
    const data = await res.json()
    setTranscript(data.text || data.transcript || '')
  }

  const handleChat = async () => {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: transcript }),
    })
    const data = await res.json()
    setAnswer(data.answer)
  }

  const handleTts = async () => {
    const res = await fetch(`${API_BASE}/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: transcript, speakerId: selectedSpeaker }),
    })
    const data = await res.json()
    setAudioUrl(`${API_BASE}${data.audioUrl}`)
  }

  return (
    <div className="app">
      <h1>Uzbek Local Voice AI TS</h1>
      <section>
        <h2>Status</h2>
        <pre>{JSON.stringify(status, null, 2)}</pre>
      </section>
      <section>
        <h2>Speaker</h2>
        <select value={selectedSpeaker} onChange={(e) => setSelectedSpeaker(e.target.value)}>
          {speakers.map((speaker) => (
            <option key={speaker.speakerId} value={speaker.speakerId}>
              {speaker.displayName}
            </option>
          ))}
        </select>
      </section>
      <section>
        <h2>Voice Chat</h2>
        <input type="file" accept="audio/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button onClick={handleUpload}>Transcribe</button>
      </section>
      <section>
        <h2>Transcript</h2>
        <textarea value={transcript} onChange={(e) => setTranscript(e.target.value)} rows={4} />
      </section>
      <section>
        <button onClick={handleChat}>Send to LLM</button>
        <button onClick={handleTts}>Synthesize</button>
      </section>
      <section>
        <h2>Answer</h2>
        <pre>{answer}</pre>
      </section>
      {audioUrl && (
        <section>
          <h2>Playback</h2>
          <audio controls src={audioUrl} />
        </section>
      )}
    </div>
  )
}

export default App
