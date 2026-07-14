from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/ai-service"))
from app.engines.llm import LocalLLMEngine


def test_health_does_not_load_a_model():
    engine = LocalLLMEngine()
    health = engine.health_check()
    assert health["loaded"] is False
    assert health["backend"] == "llama.cpp"
