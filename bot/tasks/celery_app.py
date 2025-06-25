from celery import Celery
from bot.logger import setup_logger
import os
from dotenv import load_dotenv

load_dotenv()
logger = setup_logger(__name__)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery(
    "bot",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "bot.tasks.bartender_notification",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=False,
    broker_connection_retry_on_startup=True,
    result_expires=3600,  # Expire task results after 1 hour
)

if __name__ == "__main__":
    app.start()
