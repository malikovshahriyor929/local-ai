import torch
import gradio as gr
from transformers import pipeline, VitsModel, AutoTokenizer
import numpy as np
import warnings

warnings.filterwarnings("ignore")

# Device configuration
device = "cuda:0" if torch.cuda.is_available() else "cpu"
if device == "cpu" and torch.backends.mps.is_available():
    device = "mps"

print(f"Using device: {device}")

# ==========================================
# STT Configuration
# ==========================================
stt_model_id = "openai/whisper-small"
print(f"Loading STT model: {stt_model_id}...")
stt_pipeline = pipeline(
    "automatic-speech-recognition", 
    model=stt_model_id, 
    device=device
)

def transcribe(audio_path):
    if audio_path is None:
        return "Please provide an audio input."
    
    # Whisper natively supports multiple languages. We force it to output Uzbek.
    result = stt_pipeline(audio_path, generate_kwargs={"language": "uzbek"})
    return result["text"]


# ==========================================
# TTS Configuration
# ==========================================
tts_model_id = "facebook/mms-tts-uzb-script_cyrillic"
print(f"Loading TTS model: {tts_model_id}...")
tokenizer = AutoTokenizer.from_pretrained(tts_model_id)
tts_model = VitsModel.from_pretrained(tts_model_id)
# VitsModel often does not move automatically to device in older transformers versions, so we force it:
tts_model.to(device)

def latin_to_cyrillic(text):
    """
    A simple transliterator to convert Latin Uzbek text to Cyrillic
    since the TTS model is trained on Cyrillic.
    """
    mapping = {
        "sh": "ш", "ch": "ч", "g'": "ғ", "o'": "ў", "yo": "ё", "yu": "ю", "ya": "я",
        "Sh": "Ш", "Ch": "Ч", "G'": "Ғ", "O'": "Ў", "Yo": "Ё", "Yu": "Ю", "Ya": "Я",
        "a": "а", "b": "б", "d": "д", "e": "э", "f": "ф", "g": "г", "h": "ҳ", 
        "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", 
        "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", 
        "x": "х", "y": "й", "z": "з",
        "A": "А", "B": "Б", "D": "Д", "E": "Э", "F": "Ф", "G": "Г", "H": "Ҳ", 
        "I": "И", "J": "Ж", "K": "К", "L": "Л", "M": "М", "N": "Н", "O": "О", 
        "P": "П", "Q": "Қ", "R": "Р", "S": "С", "T": "Т", "U": "У", "V": "В", 
        "X": "Х", "Y": "Й", "Z": "З", "'": "ъ"
    }
    
    # Sort keys by length descending to match multi-character strings first
    for latin, cyrillic in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(latin, cyrillic)
    return text

def synthesize(text, is_latin):
    if not text.strip():
        return None, "Please provide text."
    
    if is_latin:
        text = latin_to_cyrillic(text)
        
    inputs = tokenizer(text, return_tensors="pt").to(device)
    with torch.no_grad():
        output = tts_model(**inputs).waveform
        
    waveform = output.cpu().numpy().squeeze()
    sample_rate = tts_model.config.sampling_rate
    
    return (sample_rate, waveform)


# ==========================================
# Gradio UI Configuration
# ==========================================
with gr.Blocks(title="Uzbek Voice AI - STT & TTS") as app:
    gr.Markdown("# 🇺🇿 Uzbek Speech-to-Text & Text-to-Speech")
    gr.Markdown("An AI application for transcribing Uzbek audio to text and generating Uzbek speech from text.")
    
    with gr.Tab("Speech-to-Text (STT)"):
        gr.Markdown("Upload an audio file or record from your microphone to get the Uzbek transcription.")
        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(sources=["microphone", "upload"], label="Input Audio")
                stt_btn = gr.Button("Transcribe", variant="primary")
            with gr.Column():
                stt_output = gr.Textbox(label="Transcription Result")
        
        stt_btn.click(fn=transcribe, inputs=audio_input, outputs=stt_output)
        
    with gr.Tab("Text-to-Speech (TTS)"):
        gr.Markdown("Type text to synthesize speech. The model uses Cyrillic natively, but we've included an auto-transliterator if you type in Latin.")
        with gr.Row():
            with gr.Column():
                tts_input = gr.Textbox(lines=4, placeholder="Matnni shu yerga yozing...", label="Input Text")
                is_latin_checkbox = gr.Checkbox(label="Text is in Latin script (auto-convert to Cyrillic)", value=True)
                tts_btn = gr.Button("Synthesize", variant="primary")
            with gr.Column():
                tts_output = gr.Audio(label="Synthesized Audio")
                
        tts_btn.click(fn=synthesize, inputs=[tts_input, is_latin_checkbox], outputs=tts_output)

if __name__ == "__main__":
    print("Starting Gradio app...")
    app.launch(share=True, show_api=False)
