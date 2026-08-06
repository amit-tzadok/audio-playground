import json
import os
from typing import Optional
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from celery import Celery

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
celery = Celery(__name__, broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_audio(file: UploadFile = File(...), num_speakers: Optional[int] = Form(None)):
    # save uploaded file and enqueue processing
    dest = DATA_DIR / file.filename
    content = await file.read()
    with open(dest, "wb") as out:
        out.write(content)
    await file.close()

    task = process_audio.delay(str(dest), num_speakers)
    return JSONResponse({"filename": file.filename, "task_id": task.id})


@app.get("/status/{task_id}")
def task_status(task_id: str):
    res = celery.AsyncResult(task_id)
    return {"id": task_id, "state": res.state, "result": res.result}


@celery.task(name="process_audio")
def process_audio(path: str, num_speakers: Optional[int] = None):
    try:
        from app.diarization import diarize
        segments = diarize(path, num_speakers=num_speakers)
        return {"path": path, "segments": segments}
    except Exception as e:
        return {"path": path, "error": str(e)}
