# celery_app/tasks.py
import pendulum
from celery import shared_task
from aiogram import Bot
from db.database import async_session_maker
from db.services import get_users_by_group_id
from bot.texts import EVENT_NOTIFICATION_TEXT
from shared.config import settings
from bot.logger import setup_logger

logger = setup_logger(__name__)


@shared_task(bind=True, ignore_result=True)
async def send_notification(chat_id: int, notification_text: str):
    async with async_session_maker() as session:
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            users = await get_users_by_group_id(session, chat_id)
            successful_sends = 0
            failed_sends = 0
            for user in users:
                try:
                    await bot.send_message(user.telegram_id, notification_text)
                    successful_sends += 1
                    logger.info(f"Notification sent to user {user.telegram_id}")
                except Exception as e:
                    failed_sends += 1
                    logger.error(
                        f"Failed to send notification to user {user.telegram_id}: {e}"
                    )
            logger.info(
                f"Notification task completed: {successful_sends} successful, {failed_sends} failed"
            )
            return {"successful": successful_sends, "failed": failed_sends}
        finally:
            await bot.session.close()


@shared_task(bind=True, ignore_result=True)
async def check_birthdays():
    async with async_session_maker() as session:
        today = pendulum.now("Europe/Moscow").date()
        # Example: Query users with birthdays today (implementation depends on requirements)
        logger.info("Running birthday check task")
        # Add logic to fetch users and send birthday messages


@shared_task(bind=True, ignore_result=True)
async def hero_selection():
    logger.info("Running hero selection task")
    # Add logic for hero selection (implementation depends on requirements)
