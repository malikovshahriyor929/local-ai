from abc import ABC, abstractmethod
from typing import Optional

class BaseSTTEngine(ABC):
    @abstractmethod
    def transcribe_file(self, audio_path: str, language: str = "uz") -> str:
        raise NotImplementedError

    @abstractmethod
    def transcribe_microphone_chunk(self, audio_bytes: bytes, language: str = "uz") -> str:
        raise NotImplementedError
