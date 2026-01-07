import os
from celery import Celery

broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery("playground", broker=broker, backend=backend)
celery_app.conf.update(task_track_started=True)
