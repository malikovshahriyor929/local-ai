import io
import numpy as np
from pathlib import Path
from pydub import AudioSegment
import wave


def save_bytes_as_wav(audio_bytes: bytes, output_path: str, sample_rate: int = 16000):
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(sample_rate).set_channels(1)
    audio.export(output_path, format="wav")


def save_wav_bytes(wav_array, output_path: Path, sample_rate: int = 22050):
    if hasattr(wav_array, "dtype"):
        import soundfile as sf
        sf.write(output_path, wav_array, sample_rate)
    else:
        with output_path.open("wb") as f:
            f.write(wav_array)


def load_wav_file(audio_path: str):
    audio = AudioSegment.from_wav(audio_path)
    samples = np.array(audio.get_array_of_samples())
    return samples, audio.frame_rate
