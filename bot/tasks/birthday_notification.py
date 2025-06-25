import os
import asyncio
from celery import shared_task
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.user_repository import UserRepository
from bot.texts import BIRTHDAY_NOTIFICATION
from bot.logger import setup_logger
from db.database import get_async_session_context
from pendulum import now

from db.models import User

logger = setup_logger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def send_birthday_notification(bot: Bot, user: User, session: AsyncSession):
    if not user.birth_date or not user.registered_from_group_id:
        logger.debug(
            f"Пропущен пользователь {user.telegram_id}: нет даты рождения или группы"
        )
        return
    today = now("Europe/Moscow")
    if user.birth_date.day != today.day or user.birth_date.month != today.month:
        return
    message_text = BIRTHDAY_NOTIFICATION.format(name=user.username)
    try:
        await bot.send_message(chat_id=user.registered_from_group_id, text=message_text)
        logger.info(
            f"Поздравление отправлено для {user.name} в группу {user.registered_from_group_id}"
        )
    except Exception as e:
        logger.error(
            f"Ошибка отправки поздравления для {user.name} в группу {user.registered_from_group_id}: {e}"
        )


@shared_task(bind=True, ignore_result=True)
def process_birthday_notifications(self):
    logger.info("Запуск задачи проверки дней рождения")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def main():
        bot = Bot(token=BOT_TOKEN)
        try:
            async with get_async_session_context(loop=loop) as session:
                users = await UserRepository.get_all_users(session, limit=1000)
                for user in users:
                    await send_birthday_notification(bot, user, session)
        except Exception as e:
            logger.error(f"Ошибка в задаче проверки дней рождения: {e}", exc_info=True)
            raise self.retry(exc=e, countdown=60, max_retries=3)
        finally:
            await bot.session.close()

    try:
        loop.run_until_complete(main())
    finally:
        if not loop.is_closed():
            loop.close()
