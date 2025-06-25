from celery import Celery
from celery.schedules import crontab
from bot.logger import setup_logger
import os
from dotenv import load_dotenv
import pendulum

load_dotenv()
logger = setup_logger(__name__)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

BIRTHDAY_CHECK_TIME = os.getenv("BIRTHDAY_CHECK_TIME", "17:58")


def parse_time(time_str: str) -> dict:
    """Парсит время в формате HH:MM и возвращает словарь для crontab."""
    try:
        parsed_time = pendulum.parse(time_str, strict=False)
        hour = parsed_time.hour
        minute = parsed_time.minute
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid time values: hour={hour}, minute={minute}")
        return {"hour": hour, "minute": minute}
    except Exception as e:
        logger.error(f"Failed to parse time '{time_str}': {e}")
        raise ValueError(f"Invalid time format: {time_str}. Use HH:MM (e.g., 15:15).")


BIRTHDAY_CHECK_CRONTAB = parse_time(BIRTHDAY_CHECK_TIME)

app = Celery(
    "bot",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["bot.tasks.bartender_notification", "bot.tasks.birthday_notification"],
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
app.conf.beat_schedule = {
    "send-birthday-notifications": {
        "task": "bot.tasks.birthday_notification.process_birthday_notifications",
        "schedule": crontab(**BIRTHDAY_CHECK_CRONTAB),
    },
}

if __name__ == "__main__":
    app.start()
