from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import AsyncIterator

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import ROOT, settings
from app.engines.llm import llm_engine
from app.engines.stt import stt_engine
from app.engines.tts import tts_engine
from app.errors import LocalAIError, http_error
from app.utils.system import detect_system


class ChatRequest(BaseModel):
    conversationId: str | None = None
    messages: list[dict[str, str]] = Field(min_length=1)
    language: str = "uz"
    useKnowledgeBase: bool = False
    requestId: str | None = None


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    speakerId: str = "default"
    language: str = "uz"
    speed: float = Field(default=1, gt=0, le=2)
    emotion: str = "neutral"


def sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    llm_engine.unload_model()
    stt_engine.unload_model()
    tts_engine.unload_model()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
(ROOT / "output").mkdir(exist_ok=True)
app.mount("/audio", StaticFiles(directory=ROOT / "output"), name="audio")


@app.exception_handler(LocalAIError)
async def local_error_handler(_, exc: LocalAIError):
    return JSONResponse(status_code=503, content=exc.body())


@app.get("/api/system/health")
def health() -> dict[str, object]:
    return {"status": "ok", "offlineMode": settings.offline_mode, "system": detect_system(), "llm": llm_engine.health_check(), "stt": stt_engine.health_check(), "tts": tts_engine.health_check()}


@app.get("/api/system/models")
def models() -> dict[str, object]:
    return {"llm": llm_engine.get_model_info(), "stt": stt_engine.get_model_info(), "tts": tts_engine.get_model_info()}


@app.get("/api/llm/health")
def llm_health(): return llm_engine.health_check()

@app.get("/api/llm/model")
def llm_model(): return llm_engine.get_model_info()

@app.post("/api/llm/load")
def llm_load(): return llm_engine.load_model()

@app.post("/api/llm/unload")
def llm_unload():
    llm_engine.unload_model()
    return {"ok": True}

@app.post("/api/llm/cancel")
def llm_cancel(payload: dict[str, str]):
    llm_engine.cancel_generation(payload.get("requestId", ""))
    return {"ok": True}

@app.post("/api/llm/chat")
def llm_chat(request: ChatRequest): return llm_engine.chat(request.messages, request.requestId)

@app.post("/api/llm/chat/stream")
async def llm_stream(request: ChatRequest):
    async def events() -> AsyncIterator[str]:
        request_id = request.requestId or str(uuid.uuid4())
        yield sse("generation-start", {"requestId": request_id})
        answer = ""
        try:
            for token in llm_engine.stream_chat(request.messages, request_id):
                answer += token
                yield sse("token", {"token": token})
            yield sse("confidence", {"confidence": "low" if "ishonchli ma’lumotim yetarli emas" in answer.lower() else "medium"})
            yield sse("generation-complete", {"answer": answer, "speechText": answer})
        except LocalAIError as exc:
            yield sse("generation-error", exc.body())
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


async def save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "audio.webm").suffix.lower()
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
        raise LocalAIError("AUDIO_FORMAT_UNSUPPORTED", "Audio formati qo‘llab-quvvatlanmaydi.", suffix)
    path = Path(NamedTemporaryFile(suffix=suffix, delete=False).name)
    with path.open("wb") as destination:
        shutil.copyfileobj(file.file, destination)
    return path


@app.post("/api/stt/transcribe")
async def transcribe(file: UploadFile = File(...)):
    path = await save_upload(file)
    try: return stt_engine.transcribe(path)
    finally: path.unlink(missing_ok=True)


@app.post("/api/tts/synthesize")
def synthesize(request: TTSRequest): return tts_engine.synthesize(request.text, request.speakerId, request.language, request.speed, request.emotion)


@app.post("/api/voice-chat")
async def voice_chat(file: UploadFile = File(...), conversationId: str | None = Form(None)):
    path = await save_upload(file)
    async def events() -> AsyncIterator[str]:
        request_id = str(uuid.uuid4())
        yield sse("upload-received", {"requestId": request_id, "conversationId": conversationId})
        try:
            yield sse("stt-started", {})
            transcript = stt_engine.transcribe(path)
            yield sse("transcription-ready", transcript)
            yield sse("llm-started", {})
            answer = ""
            for token in llm_engine.stream_chat([{"role": "user", "content": str(transcript["normalizedText"])}], request_id):
                answer += token
                yield sse("answer-token", {"token": token})
            yield sse("answer-ready", {"answer": answer, "speechText": answer})
            yield sse("tts-started", {})
            audio = tts_engine.synthesize(answer)
            yield sse("audio-ready", audio)
            yield sse("complete", {"requestId": request_id})
        except LocalAIError as exc:
            yield sse("error", exc.body())
        finally:
            path.unlink(missing_ok=True)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
