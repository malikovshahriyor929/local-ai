import httpx
from typing import List, Dict
from app.llm.base import BaseLLMClient

class LocalLLMClient(BaseLLMClient):
    def __init__(self, base_url: str, model: str, system_prompt: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system_prompt = system_prompt

    def _build_payload(self, messages: List[Dict[str, str]]) -> Dict:
        return {
            "messages": [{"role": "system", "content": self.system_prompt}, *messages],
            "language": "uz",
        }

    def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        with httpx.Client(timeout=120) as client:
            response = client.post(f"{self.base_url}/api/llm/chat", json=self._build_payload(messages))
            response.raise_for_status()
            payload = response.json()
            answer = payload.get("answer")
            if not answer:
                raise RuntimeError("LLM returned no choices")
            return str(answer)

    def stream_chat_completion(self, messages: List[Dict[str, str]]):
        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{self.base_url}/api/llm/chat/stream",
                json=self._build_payload(messages),
                stream=True,
            )
            response.raise_for_status()
            for chunk in response.iter_text():
                yield chunk
