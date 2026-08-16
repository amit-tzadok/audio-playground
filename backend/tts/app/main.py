import tempfile
from pathlib import Path

import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import Response

app = FastAPI(title="playground-tts-service")

_whisper_model = None
_tts_model = None


def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_model


def get_tts():
    global _tts_model
    if _tts_model is None:
        from TTS.api import TTS
        _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
    return _tts_model


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/warmup")
def warmup():
    """Force both models to load now rather than on the first real request
    (each load is a multi-minute cost — a persistent service should pay it
    once at startup, not on whoever's request happens to be first)."""
    get_whisper()
    get_tts()
    return {"status": "warm"}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    raw = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        tmp.write(raw)
        tmp.flush()
        model = get_whisper()
        segments, info = model.transcribe(tmp.name)
        text = " ".join(s.text for s in segments).strip()
    return {"text": text, "language": info.language}


@app.post("/clone_speak")
async def clone_speak(
    reference: UploadFile = File(...),
    text: str = Form(...),
    language: str = Form("en"),
    target_duration: float = Form(None),
):
    """Synthesize `text` in the cloned voice from `reference`. If
    target_duration is given, calibrate XTTS's speed parameter over a few
    passes to land close to it — the parameter isn't perfectly linear, so
    one shot rarely hits the target exactly.
    """
    tts = get_tts()
    raw = await reference.read()
    with tempfile.TemporaryDirectory() as tmp:
        ref_path = Path(tmp) / "ref.wav"
        ref_path.write_bytes(raw)
        out_path = Path(tmp) / "out.wav"

        speed = 1.0
        if target_duration and target_duration > 0:
            for _ in range(3):
                tts.tts_to_file(
                    text=text, speaker_wav=str(ref_path), language=language,
                    file_path=str(out_path), speed=speed,
                )
                out, sr = sf.read(str(out_path))
                actual = len(out) / sr
                if abs(actual - target_duration) / target_duration < 0.08:
                    break
                speed = max(0.5, min(2.0, speed * (actual / target_duration)))
        else:
            tts.tts_to_file(
                text=text, speaker_wav=str(ref_path), language=language,
                file_path=str(out_path),
            )

        data = out_path.read_bytes()
    return Response(content=data, media_type="audio/wav")
