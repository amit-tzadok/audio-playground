import json
import mimetypes
import os
from typing import Dict, Optional
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from celery import Celery
from pydantic import BaseModel

from app import storage

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
    if tool == "url2wav":
        if not url:
            return JSONResponse({"error": "url is required"}, status_code=400)
        task = download_url_to_wav.delay(url)
        return JSONResponse({"url": url, "task_id": task.id})

    if url and not file:
        task = download_then_process.delay(url, tool, num_speakers)
        return JSONResponse({"url": url, "task_id": task.id})

    if not file:
        return JSONResponse({"error": "file is required"}, status_code=400)

    # save uploaded file and enqueue processing. When S3 is configured
    # (Kubernetes), the file has to cross into whatever pod picks up the
    # Celery task, which local disk can't do — upload it and hand the
    # task an s3:// reference instead of a local path.
    dest = DATA_DIR / file.filename
    content = await file.read()
    with open(dest, "wb") as out:
        out.write(content)
    await file.close()
    task_input = storage.finalize_path(str(dest), "uploads/")

    if tool == "remove-music":
        task = remove_background_music.delay(task_input)
        return JSONResponse({"filename": file.filename, "task_id": task.id})

    if tool == "visualization":
        task = analyze_visualization.delay(task_input)
        return JSONResponse({"filename": file.filename, "task_id": task.id})

    if tool == "audio2text":
        task = transcribe_audio_task.delay(task_input)
        return JSONResponse({"filename": file.filename, "task_id": task.id})

    if tool == "fundamental-freq":
        task = analyze_fundamental_freq.delay(task_input)
        return JSONResponse({"filename": file.filename, "task_id": task.id})

    task = process_audio.delay(task_input, num_speakers)
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
    if path and path.startswith("s3://"):
        return RedirectResponse(storage.presigned_url(path))
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


def _run_process_audio(path: str, num_speakers: Optional[int] = None):
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


def _run_remove_background_music(path: str):
    from app.separate_vocals import separate_vocals
    from app.denoise import denoise_file
    cleaned = separate_vocals(path, DATA_DIR)
    cleaned = denoise_file(cleaned, DATA_DIR)
    return {"path": cleaned, "filename": Path(cleaned).name}


def _run_analyze_visualization(path: str):
    from app.visualize import analyze_audio
    analysis = analyze_audio(path)
    return {"path": path, "filename": Path(path).name, **analysis}


def _run_transcribe(path: str):
    from app.transcribe import transcribe_audio
    transcript = transcribe_audio(path)
    return {"path": path, "filename": Path(path).name, **transcript}


def _run_analyze_fundamental_freq(path: str):
    from app.fundamental_freq import estimate_f0
    analysis = estimate_f0(path)
    return {"path": path, "filename": Path(path).name, **analysis}


# Maps a tool id to the processing function that turns a local audio path
# into that tool's result — shared between the direct file-upload tasks
# below and download_then_process, so a YouTube URL goes through the exact
# same pipeline a manually uploaded file would.
TOOL_PROCESSORS = {
    "remove-music": lambda path, num_speakers: _run_remove_background_music(path),
    "visualization": lambda path, num_speakers: _run_analyze_visualization(path),
    "audio2text": lambda path, num_speakers: _run_transcribe(path),
    "fundamental-freq": lambda path, num_speakers: _run_analyze_fundamental_freq(path),
}


def _finalize_result(result: dict) -> dict:
    """Upload a task's output file(s) to S3 (if configured) and rewrite
    the result to reference them by s3:// URI instead of a worker-pod-local
    path, so the backend pod serving /download can reach them."""
    if not isinstance(result, dict) or result.get("error"):
        return result
    if "path" in result:
        result["path"] = storage.finalize_path(result["path"], "results/")
    if isinstance(result.get("speaker_files"), dict):
        result["speaker_files"] = {
            speaker: storage.finalize_path(p, "results/")
            for speaker, p in result["speaker_files"].items()
        }
    return result


@celery.task(name="process_audio")
def process_audio(path: str, num_speakers: Optional[int] = None):
    try:
        path = storage.resolve_input(path, DATA_DIR)
        return _finalize_result(_run_process_audio(path, num_speakers))
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="remove_background_music")
def remove_background_music(path: str):
    try:
        path = storage.resolve_input(path, DATA_DIR)
        return _finalize_result(_run_remove_background_music(path))
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="analyze_visualization")
def analyze_visualization(path: str):
    try:
        path = storage.resolve_input(path, DATA_DIR)
        return _finalize_result(_run_analyze_visualization(path))
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="transcribe_audio_task")
def transcribe_audio_task(path: str):
    try:
        path = storage.resolve_input(path, DATA_DIR)
        return _finalize_result(_run_transcribe(path))
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="analyze_fundamental_freq")
def analyze_fundamental_freq(path: str):
    try:
        path = storage.resolve_input(path, DATA_DIR)
        return _finalize_result(_run_analyze_fundamental_freq(path))
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="download_then_process")
def download_then_process(url: str, tool: str, num_speakers: Optional[int] = None):
    from app.url_download import download_audio_as_wav
    try:
        path = str(download_audio_as_wav(url, DATA_DIR))
    except Exception as e:
        return {"error": f"Failed to download audio: {e}"}

    processor = TOOL_PROCESSORS.get(tool, _run_process_audio)
    try:
        return _finalize_result(processor(path, num_speakers))
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(bind=True, name="remix_speakers")
def remix_speakers(self, path: str, segments: list, speaker_rates: dict):
    try:
        path = storage.resolve_input(path, DATA_DIR)
        from app.remix import remix_conversation

        def progress_cb(done, total):
            self.update_state(state="PROGRESS", meta={"current": done, "total": total})

        out_path = remix_conversation(path, segments, speaker_rates, DATA_DIR, progress_cb=progress_cb)
        return _finalize_result({"path": out_path, "speaker_rates": speaker_rates})
    except Exception as e:
        return {"path": path, "error": str(e)}


@celery.task(name="download_url_to_wav")
def download_url_to_wav(url: str):
    try:
        from app.url_download import download_audio_as_wav
        path = download_audio_as_wav(url, DATA_DIR)
        result = {"url": url, "path": str(path), "filename": path.name}
        return _finalize_result(result)
    except Exception as e:
        return {"url": url, "error": str(e)}
