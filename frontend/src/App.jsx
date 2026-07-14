import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

function App() {
  const [status, setStatus] = useState(null)
  const [speakers, setSpeakers] = useState([])
  const [selectedSpeaker, setSelectedSpeaker] = useState('female_assistant')
  const [uploadText, setUploadText] = useState('')
  const [chatText, setChatText] = useState('')
  const [responseText, setResponseText] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [file, setFile] = useState(null)

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
    setUploadText(data.transcript || '')
  }

  const handleChat = async () => {
    const res = await fetch(`${API_BASE}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: uploadText }) })
    const data = await res.json()
    setResponseText(data.answer)
  }

  const handleSpeak = async () => {
    const res = await fetch(`${API_BASE}/speak`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: uploadText, speaker_id: selectedSpeaker }) })
    const data = await res.json()
    setAudioUrl(`${API_BASE}${data.audio_path}`)
  }

  const handleVoiceChat = async () => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API_BASE}/voice-chat?speaker_id=${selectedSpeaker}`, { method: 'POST', body: form })
    const data = await res.json()
    setUploadText(data.transcript)
    setResponseText(data.answer_text)
    setAudioUrl(`${API_BASE}${data.audio_path}`)
  }

  return (
    <div className="app-container">
      <h1>Uzbek Local Voice AI</h1>
      <section>
        <h2>Status</h2>
        <pre>{JSON.stringify(status, null, 2)}</pre>
      </section>
      <section>
        <h2>Speaker</h2>
        <select value={selectedSpeaker} onChange={(e) => setSelectedSpeaker(e.target.value)}>
          {speakers.map((speaker) => (
            <option key={speaker.speaker_id} value={speaker.speaker_id}>
              {speaker.display_name}
            </option>
          ))}
        </select>
      </section>
      <section>
        <h2>Upload Audio</h2>
        <input type="file" accept="audio/*" onChange={(e) => setFile(e.target.files?.[0])} />
        <button onClick={handleUpload}>Transcribe</button>
        <button onClick={handleVoiceChat}>Voice Chat</button>
      </section>
      <section>
        <h2>Transcript</h2>
        <textarea value={uploadText} onChange={(e) => setUploadText(e.target.value)} rows={4} />
      </section>
      <section>
        <h2>Text Chat</h2>
        <button onClick={handleChat}>Send to LLM</button>
        <button onClick={handleSpeak}>Synthesize</button>
      </section>
      <section>
        <h2>Assistant Response</h2>
        <pre>{responseText}</pre>
      </section>
      {audioUrl && (
        <section>
          <h2>Audio Playback</h2>
          <audio controls src={audioUrl} />
        </section>
      )}
    </div>
  )
}

export default App
