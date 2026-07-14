from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.stt.base import BaseSTTEngine
from app.stt.kotib_stt import KotibSTT
from app.stt.whisper_stt import FasterWhisperSTT, WhisperFallbackSTT
from app.llm.base import BaseLLMClient
from app.llm.local_llm import LocalLLMClient
from app.tts.base import BaseTTSEngine
from app.tts.matcha_tts import MatchaUzbekTTS
from app.speakers.manager import SpeakerManager
from app.utils.text_cleaner import normalize_text
from pathlib import Path
import uuid
import shutil

app = FastAPI(title="Uzbek Local Voice AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path(settings.audio_output_dir)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/audio", StaticFiles(directory=OUTPUT_DIR), name="audio")

stt_engine = None
llm_client = None
tts_engine = None
speaker_manager = SpeakerManager(Path(settings.speakers_dir))


@app.on_event("startup")
async def startup_event():
    global stt_engine, llm_client, tts_engine
    if settings.stt_engine == "kotib":
        stt_engine = KotibSTT()
    elif settings.stt_engine == "faster-whisper":
        stt_engine = FasterWhisperSTT()
    else:
        stt_engine = WhisperFallbackSTT()

    llm_client = LocalLLMClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        system_prompt=settings.system_prompt,
    )
    tts_engine = MatchaUzbekTTS()


@app.get("/health")
async def health():
    return {"status": "ok", "stt_engine": settings.stt_engine, "llm_url": settings.llm_base_url}


@app.get("/speakers")
async def get_speakers():
    return speaker_manager.list_speakers()


@app.post("/stt/file")
async def stt_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".wav", ".mp3", ".m4a", ".ogg")):
        raise HTTPException(status_code=400, detail="Unsupported file type")
    temp_path = OUTPUT_DIR / f"stt_upload_{uuid.uuid4().hex}_{file.filename}"
    with temp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    text = stt_engine.transcribe_file(str(temp_path), language=settings.stt_language)
    temp_path.unlink(missing_ok=True)
    return {"transcript": normalize_text(text)}


@app.post("/stt/mic-chunk")
async def stt_mic_chunk(chunk: UploadFile = File(...)):
    chunk_bytes = await chunk.read()
    text = stt_engine.transcribe_microphone_chunk(chunk_bytes, language=settings.stt_language)
    return {"transcript": normalize_text(text)}


@app.post("/chat")
async def chat(payload: dict):
    user_text = payload.get("text")
    if not user_text:
        raise HTTPException(status_code=400, detail="Missing text")
    response = llm_client.chat_completion([{"role": "user", "content": user_text}])
    return {"answer": response}


@app.post("/speak")
async def speak(payload: dict):
    text = payload.get("text")
    speaker_id = payload.get("speaker_id", settings.default_speaker)
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")
    speaker = speaker_manager.get_speaker(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    normalized = normalize_text(text)
    output_path = tts_engine.synthesize(normalized, speaker_id)
    return {"audio_path": f"/audio/{Path(output_path).name}", "speaker_id": speaker_id}


@app.post("/voice-chat")
async def voice_chat(file: UploadFile = File(...), speaker_id: str = settings.default_speaker):
    chunk_bytes = await file.read()
    text = stt_engine.transcribe_microphone_chunk(chunk_bytes, language=settings.stt_language)
    normalized = normalize_text(text)
    response = llm_client.chat_completion([{"role": "user", "content": normalized}])
    speaker = speaker_manager.get_speaker(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    audio_path = tts_engine.synthesize(response, speaker_id)
    return {
        "transcript": normalized,
        "answer_text": response,
        "audio_path": f"/audio/{Path(audio_path).name}",
        "speaker_id": speaker_id,
    }


@app.post("/speakers/add")
async def add_speaker(payload: dict):
    speaker_id = payload.get("speaker_id")
    display_name = payload.get("display_name")
    reference_audio = payload.get("reference_audio", "reference.wav")
    if not speaker_id or not display_name:
        raise HTTPException(status_code=400, detail="speaker_id and display_name are required")
    speaker_manager.add_speaker(
        speaker_id=speaker_id,
        display_name=display_name,
        reference_audio=reference_audio,
    )
    return {"status": "ok"}


@app.post("/dataset/validate")
async def validate_dataset(payload: dict):
    speaker_id = payload.get("speaker_id")
    if not speaker_id:
        raise HTTPException(status_code=400, detail="Missing speaker_id")
    speaker_dir = Path(settings.processed_audio_dir) / speaker_id
    if not speaker_dir.exists():
        raise HTTPException(status_code=404, detail="Speaker data not found")
    metadata = speaker_manager.validate_dataset(speaker_id)
    return {"status": "ok", "metadata_records": metadata}
