import json
import mimetypes
import os
from typing import Dict, Optional
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from celery import Celery
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="playground-audio-service")

_origins = json.loads(os.environ.get(
    "ALLOWED_ORIGINS",
    '["http://localhost:5173","http://127.0.0.1:5173"]'
))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Celery configured to use Redis broker. For local Docker use redis://redis:6379/0
celery = Celery(
    __name__,
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)
celery.conf.update(task_track_started=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_audio(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    tool: Optional[str] = Form(None),
    num_speakers: Optional[int] = Form(None),
):
    if tool == "url2wav" or (url and not file):
        if not url:
            return JSONResponse({"error": "url is required"}, status_code=400)
        task = download_url_to_wav.delay(url)
        return JSONResponse({"url": url, "task_id": task.id})

    if not file:
        return JSONResponse({"error": "file is required"}, status_code=400)

    # save uploaded file and enqueue processing
    dest = DATA_DIR / file.filename
    content = await file.read()
    with open(dest, "wb") as out:
        out.write(content)
    await file.close()

    if tool == "remove-music":
        task = remove_background_music.delay(str(dest))
        return JSONResponse({"filename": file.filename, "task_id": task.id})

    if tool == "visualization":
        task = analyze_visualization.delay(str(dest))
        return JSONResponse({"filename": file.filename, "task_id": task.id})

    if tool == "audio2text":
        task = transcribe_audio_task.delay(str(dest))
        return JSONResponse({"filename": file.filename, "task_id": task.id})

    if tool == "fundamental-freq":
        task = analyze_fundamental_freq.delay(str(dest))
        return JSONResponse({"filename": file.filename, "task_id": task.id})

    task = process_audio.delay(str(dest), num_speakers)
    return JSONResponse({"filename": file.filename, "task_id": task.id})


@app.get("/status/{task_id}")
def task_status(task_id: str):
    res = celery.AsyncResult(task_id)
    return {"id": task_id, "state": res.state, "result": res.result}


class RemixRequest(BaseModel):
    speaker_rates: Dict[str, float] = {}


@app.post("/remix/{task_id}")
def remix(task_id: str, req: RemixRequest):
    res = celery.AsyncResult(task_id)
    if res.state != "SUCCESS" or not isinstance(res.result, dict) or "segments" not in res.result:
        return JSONResponse({"error": "diarization result not ready"}, status_code=404)
    task = remix_speakers.delay(res.result["path"], res.result["segments"], req.speaker_rates)
    return JSONResponse({"task_id": task.id})


class InterpretRequest(BaseModel):
    instruction: str


@app.post("/interpret/{task_id}")
def interpret(task_id: str, req: InterpretRequest):
    res = celery.AsyncResult(task_id)
    if res.state != "SUCCESS" or not isinstance(res.result, dict) or "segments" not in res.result:
        return JSONResponse({"error": "diarization result not ready"}, status_code=404)
    try:
        from app.nlu import interpret_instruction
        return JSONResponse(interpret_instruction(req.instruction, res.result["segments"]))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def _serve_audio_file(path: str):
    if not path or not os.path.isfile(path):
        return JSONResponse({"error": "file no longer exists"}, status_code=404)
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return FileResponse(path, filename=Path(path).name, media_type=media_type)


@app.get("/download/{task_id}")
def download_result(task_id: str):
    res = celery.AsyncResult(task_id)
    if res.state != "SUCCESS" or not isinstance(res.result, dict) or "path" not in res.result:
        return JSONResponse({"error": "result not ready"}, status_code=404)
    return _serve_audio_file(res.result["path"])


@app.get("/download/{task_id}/speaker/{speaker}")
def download_speaker_track(task_id: str, speaker: str):
    res = celery.AsyncResult(task_id)
    if res.state != "SUCCESS" or not isinstance(res.result, dict):
        return JSONResponse({"error": "result not ready"}, status_code=404)
    path = (res.result.get("speaker_files") or {}).get(speaker)
    if not path:
        return JSONResponse({"error": "no such speaker track"}, status_code=404)
    return _serve_audio_file(path)


@celery.task(name="process_audio")
def process_audio(path: str, num_speakers: Optional[int] = None):
    try:
        from app.diarization import diarize, extract_speaker_tracks
        try:
            from app.separate_vocals import separate_vocals
            path = separate_vocals(path, DATA_DIR)
        except Exception as e:
            print(f"separate_vocals: failed, continuing without it ({e})")
        try:
            from app.denoise import denoise_file
            path = denoise_file(path, DATA_DIR)
        except Exception as e:
            print(f"denoise: failed, continuing with original audio ({e})")
        segments = diarize(path, num_speakers=num_speakers)
        speaker_files = extract_speaker_tracks(path, segments, DATA_DIR)
        return {"path": path, "segments": segments, "speaker_files": speaker_files}
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="remove_background_music")
def remove_background_music(path: str):
    try:
        from app.separate_vocals import separate_vocals
        from app.denoise import denoise_file
        cleaned = separate_vocals(path, DATA_DIR)
        cleaned = denoise_file(cleaned, DATA_DIR)
        return {"path": cleaned, "filename": Path(cleaned).name}
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="analyze_visualization")
def analyze_visualization(path: str):
    try:
        from app.visualize import analyze_audio
        analysis = analyze_audio(path)
        return {"path": path, "filename": Path(path).name, **analysis}
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="transcribe_audio_task")
def transcribe_audio_task(path: str):
    try:
        from app.transcribe import transcribe_audio
        transcript = transcribe_audio(path)
        return {"path": path, "filename": Path(path).name, **transcript}
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="analyze_fundamental_freq")
def analyze_fundamental_freq(path: str):
    try:
        from app.fundamental_freq import estimate_f0
        analysis = estimate_f0(path)
        return {"path": path, "filename": Path(path).name, **analysis}
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(bind=True, name="remix_speakers")
def remix_speakers(self, path: str, segments: list, speaker_rates: dict):
    try:
        from app.remix import remix_conversation

        def progress_cb(done, total):
            self.update_state(state="PROGRESS", meta={"current": done, "total": total})

        out_path = remix_conversation(path, segments, speaker_rates, DATA_DIR, progress_cb=progress_cb)
        return {"path": out_path, "speaker_rates": speaker_rates}
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="download_url_to_wav")
def download_url_to_wav(url: str):
    try:
        from app.url_download import download_audio_as_wav
        path = download_audio_as_wav(url, DATA_DIR)
        return {"url": url, "path": str(path), "filename": path.name}
    except Exception as e:
        return {"url": url, "error": str(e)}
