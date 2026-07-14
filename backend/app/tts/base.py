from abc import ABC, abstractmethod
from typing import List

class BaseTTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str, speaker_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def list_speakers(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def add_speaker(self, speaker_id: str, speaker_config: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove_speaker(self, speaker_id: str) -> None:
        raise NotImplementedError
