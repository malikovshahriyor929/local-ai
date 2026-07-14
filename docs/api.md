# API.md

## Endpoints

### GET /health

Returns service status.

### GET /speakers

Returns available speaker profiles.

### POST /stt/file

Upload audio and receive transcription.
- multipart/form-data: `file`

### POST /stt/mic-chunk

Upload small audio chunk and receive transcription.
- multipart/form-data: `chunk`

### POST /chat

Send text to local LLM.
- JSON: `{ "text": "..." }`

### POST /speak

Synthesize text with a speaker.
- JSON: `{ "text": "...", "speaker_id": "female_assistant" }`

### POST /voice-chat

Upload audio, run STT, chat with LLM, and synthesize answer.
- multipart/form-data: `file`
- query param: `speaker_id`

### POST /speakers/add

Add a new speaker profile.
- JSON: `{ "speaker_id": "shahriyor", "display_name": "Shahriyor Voice" }`

### POST /dataset/validate

Validate speaker dataset metadata.
- JSON: `{ "speaker_id": "shahriyor" }`
