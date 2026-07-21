from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.config import settings
from app.errors import LocalAIError

SYSTEM_PROMPT = """Siz mahalliy o‘zbek ovozli yordamchisiz. Har doim o‘zbek lotin yozuvida tabiiy va aniq javob bering. Fakt to‘qimang. Ishonchli ma’lumot bo‘lmasa, aynan shuni ayting: “Bu savol bo‘yicha ishonchli ma’lumotim yetarli emas.” Internetga kira olishingizni aytmang. Yashirin fikrlash jarayonini oshkor qilmang. Odatda 2–5 qisqa jumla bilan javob bering; ro‘yxatni faqat foydalanuvchi so‘rasa yoki u ma’lumotni aniqroq qilsa ishlating. Ovozli javoblar qisqa va suhbatga mos bo‘lsin."""


class LocalLLMEngine:
    """A single, locked llama-cpp-python model instance loaded from this repository."""
    def __init__(self) -> None:
        self._model: Any | None = None
        self._lock = threading.Lock()
        self._cancelled: set[str] = set()

    @property
    def model_path(self) -> Path:
        return settings.path(settings.llm_model_path)

    def load_model(self) -> dict[str, object]:
        if self._model is not None:
            return self.get_model_info()
        with self._lock:
            if self._model is not None:
                return self.get_model_info()
            if not self.model_path.is_file():
                raise LocalAIError("LLM_MODEL_NOT_FOUND", "Mahalliy LLM modeli topilmadi.", str(self.model_path))
            if self.model_path.suffix.lower() != ".gguf":
                raise LocalAIError("LLM_MODEL_INVALID", "LLM modeli GGUF formatida bo‘lishi kerak.", str(self.model_path))
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise LocalAIError("LLAMA_CPP_UNAVAILABLE", "llama-cpp-python o‘rnatilmagan yoki mos backend bilan yig‘ilmagan.", str(exc), True) from exc
            try:
                self._model = Llama(model_path=str(self.model_path), n_ctx=settings.llm_context_size, n_gpu_layers=settings.llm_gpu_layers, n_threads=settings.llm_threads, n_batch=settings.llm_batch_size, verbose=False)
            except Exception as exc:
                raise LocalAIError("LLM_LOAD_FAILED", "Mahalliy LLM modeli yuklanmadi.", str(exc), True) from exc
        return self.get_model_info()

    def unload_model(self) -> None:
        with self._lock:
            self._model = None

    def _require_model(self) -> Any:
        return self._model if self._model is not None else self.load_model() and self._model

    def _messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        return [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

    def stream_chat(self, messages: list[dict[str, str]], request_id: str | None = None) -> Iterator[str]:
        model = self._require_model()
        request_id = request_id or str(uuid.uuid4())
        stream = model.create_chat_completion(messages=self._messages(messages), temperature=settings.llm_temperature, top_p=settings.llm_top_p, max_tokens=settings.llm_max_tokens, stream=True)
        for packet in stream:
            if request_id in self._cancelled:
                self._cancelled.discard(request_id)
                raise LocalAIError("GENERATION_CANCELLED", "Javob yaratish to‘xtatildi.")
            token = packet.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if token:
                yield token

    def chat(self, messages: list[dict[str, str]], request_id: str | None = None) -> dict[str, object]:
        answer = "".join(self.stream_chat(messages, request_id)).strip()
        unknown = "ishonchli ma’lumotim yetarli emas" in answer.lower()
        return {"answer": answer, "speechText": answer, "confidence": "low" if unknown else "medium", "knowledgeStatus": "unknown" if unknown else "known", "reason": "Mahalliy model javobi.", "sources": []}

    def tokenize(self, text: str) -> list[int]:
        return list(self._require_model().tokenize(text.encode("utf-8")))

    def count_tokens(self, text: str) -> int:
        return len(self.tokenize(text))

    def cancel_generation(self, request_id: str) -> None:
        self._cancelled.add(request_id)

    def health_check(self) -> dict[str, object]:
        return {"loaded": self._model is not None, "modelExists": self.model_path.is_file(), "backend": settings.llm_backend}

    def get_model_info(self) -> dict[str, object]:
        return {"loaded": self._model is not None, "path": str(self.model_path), "sizeBytes": self.model_path.stat().st_size if self.model_path.is_file() else 0, "backend": settings.llm_backend, "contextSize": settings.llm_context_size}


llm_engine = LocalLLMEngine()
