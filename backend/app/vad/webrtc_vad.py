import webrtcvad
from pathlib import Path
from app.utils.audio_utils import load_wav_file

class WebRTCVAD:
    def __init__(self, aggressiveness: int = 2):
        self.vad = webrtcvad.Vad(aggressiveness)

    def detect_speech(self, audio_path: str):
        samples, sample_rate = load_wav_file(audio_path)
        if sample_rate != 16000:
            raise ValueError("WebRTC VAD requires 16kHz mono audio")
        frames = [samples[i:i+320] for i in range(0, len(samples), 320)]
        speech_frames = [self.vad.is_speech(frame.tobytes(), sample_rate) for frame in frames]
        return speech_frames
