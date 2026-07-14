# DATASET_GUIDE

## Uzbek voice dataset requirements

- Record in a quiet room.
- Use one speaker only.
- No background music or other voices.
- Speak clearly and naturally.
- Aim for 3–12 second utterances.

## File format

- WAV
- Mono
- 22050 Hz or 24000 Hz
- One sentence per file

## Directory layout

```
data/processed_audio/shahriyor/wavs/
000001.wav
000002.wav
metadata.csv
```

## metadata.csv format

```
000001.wav|Assalomu alaykum, bugun sizga qanday yordam bera olaman?
000002.wav|Bugungi darsimiz moliya bo‘limi haqida bo‘ladi.
```

## Recording tips

- Use a good USB microphone.
- Keep the mic 10-20 cm from your mouth.
- Use short Uzbek sentences with punctuation.
- Use both Latin and Cyrillic forms if you want broad coverage.

## Dataset preparation steps

1. Record raw audio into `data/raw_audio/`.
2. Use `python backend/scripts/prepare_dataset.py --source data/raw_audio --dest data/processed_audio/shahriyor/wavs`.
3. Create `metadata.csv` with file names and transcripts.
4. Validate with `/dataset/validate` endpoint.
