# celery_app/celery_app.py
import os
import pendulum
from celery.schedules import crontab
from . import celery_app
from bot.logger import setup_logger

logger = setup_logger(__name__)

HERO_SELECTION_TIME = os.getenv("HERO_SELECTION_TIME", "09:01")
BIRTHDAY_CHECK_TIME = os.getenv("BIRTHDAY_CHECK_TIME", "00:01")


def parse_time(time_str: str) -> dict:
    parsed_time = pendulum.parse(time_str, strict=False, tz="Europe/Moscow")
    return {"hour": parsed_time.hour, "minute": parsed_time.minute}


HERO_SELECTION_CRONTAB = parse_time(HERO_SELECTION_TIME)
BIRTHDAY_CHECK_CRONTAB = parse_time(BIRTHDAY_CHECK_TIME)

celery_app.conf.beat_schedule = {
    "check-birthdays": {
        "task": "celery_app.tasks.check_birthdays",
        "schedule": crontab(**BIRTHDAY_CHECK_CRONTAB),
    },
    "hero-selection": {
        "task": "celery_app.tasks.hero_selection",
        "schedule": crontab(**HERO_SELECTION_CRONTAB),
    },
}

logger.info("Celery Beat schedule configured")
