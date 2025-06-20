from celery import Celery
from shared.config import settings

celery_app = Celery("app", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.task_routes = {"celery_app.tasks.*": {"queue": "default"}}
