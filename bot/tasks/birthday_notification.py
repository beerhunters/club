from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.database import get_async_session
from bot.repositories.user_repo import UserRepository
from bot.repositories.group_user_repo import GroupUserRepository
from bot.utils.logger import setup_logger
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
import pendulum
from sqlalchemy import select
from bot.core.models import Group, GroupUser
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
logger = setup_logger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Текстовые сообщения
BIRTHDAY_MESSAGE = "🎉 Сегодня день рождения у {mentions}! Поздравляем с праздником! 🥳"
NO_BIRTHDAY_MESSAGE = "Сегодня нет именинников. 😊"


@shared_task(bind=True, ignore_result=True)
def check_birthdays(self):
    """Проверяет дни рождения пользователей и отправляет поздравления в группы."""
    logger.info("Processing daily birthday check task")
    bot = None
    try:
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN is not set in environment variables")
            raise ValueError("BOT_TOKEN is not set")

        bot = Bot(token=BOT_TOKEN)

        async def run():
            async for session in get_async_session():
                try:
                    today = pendulum.now("Europe/Moscow").date()
                    # Находим пользователей, у которых сегодня день рождения
                    users = await UserRepository.get_users_by_birthday(
                        session, today.day, today.month
                    )
                    if not users:
                        logger.info("No birthdays today")
                        return

                    # Для каждого пользователя находим группы, в которых он состоит
                    birthday_users = {user.id: user for user in users}
                    user_ids = list(birthday_users.keys())

                    # Получаем все группы, где есть эти пользователи
                    stmt = (
                        select(Group, GroupUser)
                        .join(GroupUser, Group.id == GroupUser.group_id)
                        .where(GroupUser.user_id.in_(user_ids))
                    )
                    result = await session.execute(stmt)
                    group_users = result.all()

                    # Группируем пользователей по группам
                    groups_birthdays = {}
                    for group, group_user in group_users:
                        if group.chat_id not in groups_birthdays:
                            groups_birthdays[group.chat_id] = []
                        groups_birthdays[group.chat_id].append(
                            birthday_users[group_user.user_id]
                        )

                    # Отправляем сообщения в каждую группу
                    for chat_id, birthday_users in groups_birthdays.items():
                        mentions = ", ".join(
                            [
                                f"@{user.username}" if user.username else user.name
                                for user in birthday_users
                            ]
                        )
                        message_text = BIRTHDAY_MESSAGE.format(mentions=mentions)
                        try:
                            await bot.send_message(chat_id=chat_id, text=message_text)
                            logger.info(
                                f"Sent birthday message to group {chat_id}: {message_text}"
                            )
                        except TelegramAPIError as e:
                            logger.error(
                                f"Failed to send birthday message to group {chat_id}: {e}"
                            )
                except Exception as e:
                    logger.error(f"Error processing birthday check: {e}", exc_info=True)
                    raise

        # Запускаем асинхронную функцию в текущем цикле событий
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())
    except Exception as e:
        logger.error(f"Error in check_birthdays task: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    finally:
        if bot:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(bot.session.close())
