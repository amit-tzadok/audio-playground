# Backend (FastAPI + Celery)

Run locally (requires Python + Redis) or use Docker Compose.

Locally (after activating your conda env):
```bash
pip install -r backend/requirements.txt
# start Redis separately (or use docker)
uvicorn backend.app.main:app --reload
# start a celery worker in another terminal:
celery -A backend.app.main.celery worker --loglevel=info
```

With Docker Compose:
```bash
docker compose up --build
# service available at http://localhost:8000
```

API endpoints:
- `GET /health` : health check
- `POST /upload` : multipart file upload, returns `task_id`
- `GET /status/{task_id}` : check processing status
