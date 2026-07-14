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
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                *messages,
            ],
            "temperature": 0.7,
        }

    def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        with httpx.Client(timeout=120) as client:
            response = client.post(f"{self.base_url}/v1/chat/completions", json=self._build_payload(messages))
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices", [])
            if not choices:
                raise RuntimeError("LLM returned no choices")
            return choices[0].get("message", {}).get("content", "")

    def stream_chat_completion(self, messages: List[Dict[str, str]]):
        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{self.base_url}/v1/chat/completions",
                json=self._build_payload(messages),
                stream=True,
            )
            response.raise_for_status()
            for chunk in response.iter_text():
                yield chunk
