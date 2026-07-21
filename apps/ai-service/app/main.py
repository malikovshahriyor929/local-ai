from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import time
import uuid
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import AsyncIterator

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.actions.executor import execute_plan
from app.actions.plan import ActionPlan, PlanRejected, validate_plan
from app.actions.planner import make_plan
from app.config import ROOT, settings
from app.engines.llm import llm_engine
from app.engines.stt import stt_engine
from app.engines.tts import tts_engine
from app.errors import LocalAIError, http_error
from app.utils.system import detect_system

VOICE_JOBS: dict[str, dict[str, object]] = {}
DATASET_SENTENCES = [
    "Assalomu alaykum, ismingiz nima?",
    "Bugun ob-havo juda yaxshi.",
    "Rahmat, sizga ham yaxshi kunlar tilayman.",
    "Men o‘zbek tilida ravon gapirishni o‘rganmoqdaman.",
    "Mahalliy sun’iy intellekt internetga ulanmasdan ishlaydi.",
    "Har bir yozuvni tinch joyda va bir xil ohangda ayting.",
]


def voice_id(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9_-]{2,48}", value):
        raise LocalAIError("VOICE_ID_INVALID", "Voice nomi faqat kichik harf, raqam, _ va - dan iborat bo‘lishi kerak.")
    return value


def dataset_dir(speaker_id: str) -> Path:
    return ROOT / "data" / "processed_audio" / voice_id(speaker_id)


def dataset_rows(speaker_id: str) -> list[dict[str, object]]:
    path = dataset_dir(speaker_id) / "metadata.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def write_dataset_artifacts(speaker_id: str) -> list[dict[str, object]]:
    rows = dataset_rows(speaker_id)
    root = dataset_dir(speaker_id)
    profile_path = ROOT / "data" / "speakers" / speaker_id / "speaker.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    ref_audio = str((profile_path.parent / profile["reference_audio"]).resolve())
    raw_rows = [{"audio": row["audio"], "text": row["text"], "ref_audio": ref_audio} for row in rows]
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in raw_rows)
    (root / "train_raw.jsonl").write_text(payload, encoding="utf-8")
    (root / "train.jsonl").write_text(payload, encoding="utf-8")
    return raw_rows


class ChatRequest(BaseModel):
    conversationId: str | None = None
    messages: list[dict[str, str]] = Field(min_length=1)
    language: str = "uz"
    useKnowledgeBase: bool = False
    requestId: str | None = None


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    speakerId: str = settings.tts_default_speaker
    language: str = "uz"
    speed: float = Field(default=1, gt=0, le=2)
    emotion: str = "neutral"


class ActionPlanRequest(BaseModel):
    text: str = Field(min_length=1)


class ActionExecuteRequest(BaseModel):
    plan: ActionPlan
    confirmed: bool = False


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


@app.post("/api/actions/plan")
def plan_action(request: ActionPlanRequest):
    plan, source = make_plan(request.text)
    return {"plan": plan.model_dump(), "source": source, "isConversational": plan.is_conversational()}


@app.post("/api/actions/execute")
def run_action(request: ActionExecuteRequest):
    try:
        plan = validate_plan(request.plan)
    except PlanRejected as exc:
        raise LocalAIError("PLAN_REJECTED", f"Reja qabul qilinmadi: {exc}") from exc
    if plan.requiresConfirmation and not request.confirmed:
        return {"executed": False, "needsConfirmation": True, "plan": plan.model_dump(), "results": []}
    results = execute_plan(plan)
    return {"executed": True, "needsConfirmation": False, "plan": plan.model_dump(), "results": results, "ok": all(r["ok"] for r in results)}


@app.post("/api/tts/reference-audio")
async def save_tts_reference_audio(file: UploadFile = File(...), consent: bool = Form(False)):
    if not consent:
        raise LocalAIError("VOICE_REFERENCE_CONSENT_REQUIRED", "Ovoz namunasini saqlash uchun rozilik kerak.")
    path = await save_upload(file)
    try:
        return tts_engine.save_authorized_reference(path)
    finally:
        path.unlink(missing_ok=True)


@app.get("/api/voices")
def list_voices():
    root = ROOT / "data" / "speakers"
    voices = []
    for config_path in root.glob("*/speaker.json"):
        profile = json.loads(config_path.read_text(encoding="utf-8"))
        speaker_id = str(profile["speaker_id"])
        reference = config_path.parent / str(profile.get("reference_audio", "reference.wav"))
        voices.append({
            **profile,
            "referenceReady": reference.is_file(),
            "datasetCount": len(dataset_rows(speaker_id)),
            "active": tts_engine._active_speaker() == speaker_id,
        })
    return {"voices": voices, "sentences": DATASET_SENTENCES}


@app.post("/api/voices")
def create_voice(payload: dict[str, str]):
    speaker_id = voice_id(payload.get("speakerId", "shahriyor"))
    if speaker_id != "shahriyor":
        raise LocalAIError("VOICE_NAME_REQUIRED", "Bu sahifa `shahriyor` nomli speaker yaratadi.")
    speaker_dir = ROOT / "data" / "speakers" / speaker_id
    speaker_dir.mkdir(parents=True, exist_ok=True)
    config = speaker_dir / "speaker.json"
    if not config.exists():
        config.write_text(json.dumps({"speaker_id": speaker_id, "display_name": "Shahriyor", "type": "zero_shot_clone", "language": "uz", "reference_audio": "reference.wav", "reference_transcript": "", "permission": "owned_by_user"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"speakerId": speaker_id}


@app.post("/api/voices/{speaker_id}/reference")
async def save_voice_reference(speaker_id: str, file: UploadFile = File(...), transcript: str = Form(""), autoTranscribe: bool = Form(False), consent: bool = Form(False)):
    speaker_id = voice_id(speaker_id)
    if not consent:
        raise LocalAIError("VOICE_REFERENCE_CONSENT_REQUIRED", "Ovoz namunasini ishlatish uchun rozilik kerak.")
    path = await save_upload(file)
    try:
        text = transcript.strip()
        if autoTranscribe and not text:
            text = str(stt_engine.transcribe(path)["normalizedText"])
        if not text:
            raise LocalAIError("REFERENCE_TRANSCRIPT_REQUIRED", "Reference audio uchun aniq transcript kiriting yoki avtomatik aniqlashni tanlang.")
        return {**tts_engine.save_authorized_reference(path, speaker_id, text), "referenceTranscript": text}
    finally:
        path.unlink(missing_ok=True)


@app.post("/api/voices/{speaker_id}/activate")
def activate_voice(speaker_id: str):
    tts_engine.set_active_speaker(voice_id(speaker_id))
    return {"activeSpeaker": speaker_id}


@app.post("/api/voices/{speaker_id}/test")
def test_voice(speaker_id: str, payload: dict[str, str]):
    return tts_engine.synthesize(payload.get("text", "Salom, bu mening mahalliy ovoz sinovim."), voice_id(speaker_id), "auto")


@app.get("/api/voices/{speaker_id}/dataset")
def get_voice_dataset(speaker_id: str):
    return {"sentences": DATASET_SENTENCES, "records": dataset_rows(voice_id(speaker_id))}


@app.post("/api/voices/{speaker_id}/dataset/clip")
async def save_dataset_clip(speaker_id: str, file: UploadFile = File(...), sentenceIndex: int = Form(...), text: str = Form(...)):
    speaker_id = voice_id(speaker_id)
    if not 0 <= sentenceIndex < len(DATASET_SENTENCES) or text.strip() != DATASET_SENTENCES[sentenceIndex]:
        raise LocalAIError("DATASET_TRANSCRIPT_INVALID", "Dataset transcripti ko‘rsatilgan Uzbek jumlaga aynan mos bo‘lishi kerak.")
    source = await save_upload(file)
    root = dataset_dir(speaker_id)
    wavs = root / "wavs"
    wavs.mkdir(parents=True, exist_ok=True)
    destination = wavs / f"{sentenceIndex + 1:06d}.wav"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(destination)], check=True, capture_output=True, text=True)
        with wave.open(str(destination), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
            frames = audio.readframes(audio.getnframes())
        import array
        samples = array.array("h", frames)
        peak = max((abs(sample) / 32768 for sample in samples), default=0.0)
        rms = (sum((sample / 32768) ** 2 for sample in samples) / max(len(samples), 1)) ** 0.5
        quality = {"durationSeconds": round(duration, 2), "peak": round(peak, 3), "rms": round(rms, 4), "silence": rms < 0.003, "clipping": peak >= 0.99}
        rows = [row for row in dataset_rows(speaker_id) if row.get("sentenceIndex") != sentenceIndex]
        rows.append({"sentenceIndex": sentenceIndex, "audio": str(destination.resolve()), "text": text.strip(), "quality": quality})
        rows.sort(key=lambda row: int(row["sentenceIndex"]))
        (root / "metadata.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        write_dataset_artifacts(speaker_id)
        return {"record": next(row for row in rows if row.get("sentenceIndex") == sentenceIndex), "quality": quality, "count": len(rows)}
    finally:
        source.unlink(missing_ok=True)


@app.post("/api/voices/{speaker_id}/dataset/extract-codes")
async def extract_audio_codes(speaker_id: str):
    speaker_id = voice_id(speaker_id)
    root = dataset_dir(speaker_id)
    write_dataset_artifacts(speaker_id)
    job_id = uuid.uuid4().hex
    command = ["uv", "run", "--project", str(ROOT / "apps" / "ai-service"), "--extra", "tts-finetune", "python", str(ROOT / "apps" / "ai-service" / "finetuning" / "prepare_data.py"), "--input_jsonl", str(root / "train_raw.jsonl"), "--output_jsonl", str(root / "train_with_codes.jsonl"), "--tokenizer_model_path", str(ROOT / "models" / "tts" / "qwen3-tts-base" / "speech_tokenizer")]
    VOICE_JOBS[job_id] = {"status": "queued", "command": command}
    async def run():
        VOICE_JOBS[job_id]["status"] = "running"
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        output, _ = await process.communicate()
        VOICE_JOBS[job_id].update({"status": "complete" if process.returncode == 0 else "failed", "log": output.decode(errors="replace")[-8000:]})
    asyncio.create_task(run())
    return {"jobId": job_id}


@app.get("/api/voices/jobs/{job_id}")
def voice_job(job_id: str):
    return VOICE_JOBS.get(job_id, {"status": "missing"})


@app.post("/api/voices/{speaker_id}/training/smoke-test")
async def run_smoke_test(speaker_id: str):
    speaker_id = voice_id(speaker_id)
    if len(dataset_rows(speaker_id)) < 2:
        raise LocalAIError("DATASET_TOO_SMALL", "Smoke test uchun kamida 2 ta qabul qilingan yozuv kerak.")
    job_id = uuid.uuid4().hex
    command = ["uv", "run", "--project", str(ROOT / "apps" / "ai-service"), "--extra", "tts-finetune", "python", str(ROOT / "scripts" / "train_tts_uzbek.py"), "--speaker-id", speaker_id, "--smoke-test"]
    VOICE_JOBS[job_id] = {"status": "queued", "command": command}
    async def run():
        VOICE_JOBS[job_id]["status"] = "running"
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        output, _ = await process.communicate()
        VOICE_JOBS[job_id].update({"status": "complete" if process.returncode == 0 else "failed", "log": output.decode(errors="replace")[-8000:]})
    asyncio.create_task(run())
    return {"jobId": job_id}


@app.post("/api/voices/{speaker_id}/training/activate")
def activate_fine_tuned_checkpoint(speaker_id: str, payload: dict[str, str]):
    """Make a completed local checkpoint the assistant's real TTS model."""
    speaker_id = voice_id(speaker_id)
    requested = Path(payload.get("checkpoint", ""))
    checkpoint = requested if requested.is_absolute() else ROOT / requested
    try:
        checkpoint = checkpoint.resolve(strict=True)
        checkpoint.relative_to((ROOT / "models" / "tts").resolve())
    except (FileNotFoundError, ValueError) as exc:
        raise LocalAIError("CHECKPOINT_INVALID", "Checkpoint faqat models/tts ichidan tanlanishi mumkin.") from exc
    if not (checkpoint / "config.json").is_file():
        raise LocalAIError("CHECKPOINT_INCOMPLETE", "Checkpoint config.json topilmadi.", str(checkpoint))
    config_path, profile = tts_engine._speaker_config(speaker_id)
    profile.update({
        "type": "fine_tuned",
        "model_path": str(checkpoint.relative_to(ROOT)),
        "checkpoint_activated_at": time.time(),
    })
    config_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    tts_engine.set_active_speaker(speaker_id)
    # A later synthesis loads this checkpoint instead of retaining Base weights.
    tts_engine.unload_model()
    return {"activeSpeaker": speaker_id, "checkpoint": str(checkpoint.relative_to(ROOT))}


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
            spoken = str(transcript["normalizedText"])

            # A command is announced first, then carried out. Only when the
            # request is not an action does this fall through to plain chat.
            plan = None
            try:
                plan, source = make_plan(spoken)
                if plan.is_conversational():
                    plan = None
                else:
                    yield sse("plan-ready", {"plan": plan.model_dump(), "source": source})
            except LocalAIError as exc:
                yield sse("plan-skipped", exc.body())

            if plan is not None:
                answer = plan.summary
                yield sse("answer-ready", {"answer": answer, "speechText": answer})
                yield sse("tts-started", {})
                yield sse("audio-ready", tts_engine.synthesize(answer))
                if plan.requiresConfirmation:
                    yield sse("confirmation-required", {"plan": plan.model_dump()})
                else:
                    yield sse("action-started", {})
                    results = execute_plan(plan)
                    yield sse("action-complete", {"results": results, "ok": all(r["ok"] for r in results)})
                yield sse("complete", {"requestId": request_id})
                return

            yield sse("llm-started", {})
            answer = ""
            for token in llm_engine.stream_chat([{"role": "user", "content": spoken}], request_id):
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
