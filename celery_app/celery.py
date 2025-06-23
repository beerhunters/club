from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv
from bot.utils.logger import setup_logger
import pendulum

load_dotenv()

logger = setup_logger(__name__)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Время запуска задач в формате HH:MM
HERO_SELECTION_TIME = os.getenv("HERO_SELECTION_TIME", "09:01")
BIRTHDAY_CHECK_TIME = os.getenv("BIRTHDAY_CHECK_TIME", "00:01")


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


# Парсим времена при загрузке модуля
HERO_SELECTION_CRONTAB = parse_time(HERO_SELECTION_TIME)
BIRTHDAY_CHECK_CRONTAB = parse_time(BIRTHDAY_CHECK_TIME)

app = Celery(
    "bot",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "bot.tasks.bartender_notification",
        "bot.tasks.hero_notification",
        "bot.tasks.birthday_notification",
        "celery_app.tasks",  # Include new tasks module
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=False,
    beat_schedule={
        "select-hero-every-day": {
            "task": "bot.tasks.hero_notification.process_hero_selection",
            "schedule": crontab(**HERO_SELECTION_CRONTAB),
        },
        "check-birthdays-every-day": {
            "task": "bot.tasks.birthday_notification.check_birthdays",
            "schedule": crontab(**BIRTHDAY_CHECK_CRONTAB),
        },
    },
    beat_dburi=REDIS_URL,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
)

if __name__ == "__main__":
    app.start()
