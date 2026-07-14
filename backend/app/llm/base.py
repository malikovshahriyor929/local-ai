from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseLLMClient(ABC):
    @abstractmethod
    def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError

    @abstractmethod
    def stream_chat_completion(self, messages: List[Dict[str, str]]):
        raise NotImplementedError
