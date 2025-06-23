from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.database import get_async_session
from bot.repositories.group_user_repo import GroupUserRepository
from bot.utils.logger import setup_logger
from aiogram import Bot
from bot.core.models import Group, HeroSelection, User
from sqlalchemy import select
import pendulum
import os
import asyncio
from dotenv import load_dotenv
from random import choice

load_dotenv()
logger = setup_logger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Текстовые сообщения
HERO_NOTIFICATION_INTRO_MESSAGES = [
    "🔍 Ищу героя дня для группы...",
    "🕵️‍♂️ Выбираю, кто станет героем сегодня...",
    "✨ Пора объявить героя дня!",
    "🎯 Определяю героя для этой группы...",
]
HERO_NOTIFICATION_SEARCH_MESSAGE = "⏳ Идет поиск героя..."
HERO_NOTIFICATION_SUCCESS_MESSAGE = "🏆 Герой дня в группе: @{username}!"
HERO_NOTIFICATION_ERROR_MESSAGE = (
    "❌ Ошибка при выборе героя для группы {chat_id}: {error}"
)


async def send_hero_notification(
    bot: Bot, chat_id: int, hero: "HeroSelection", user: "User"
):
    try:
        # Отправляем случайное предисловие
        intro_message = choice(HERO_NOTIFICATION_INTRO_MESSAGES)
        await bot.send_message(chat_id=chat_id, text=intro_message)

        # Имитация поиска
        await bot.send_message(chat_id=chat_id, text=HERO_NOTIFICATION_SEARCH_MESSAGE)
        await asyncio.sleep(1.5)  # Задержка для эффекта поиска

        # Отправляем сообщение с героем
        message_text = HERO_NOTIFICATION_SUCCESS_MESSAGE.format(
            username=user.username or user.name
        )
        await bot.send_message(chat_id=chat_id, text=message_text)
        logger.info(
            f"Hero notification sent for group {chat_id}: user {user.telegram_id}"
        )
    except Exception as e:
        logger.error(
            f"Error sending hero notification for group {chat_id}: {e}", exc_info=True
        )
        raise


@shared_task(bind=True, ignore_result=True)
def process_hero_selection(self):
    logger.info("Processing daily hero selection task")
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
                    result = await session.execute(select(Group))
                    groups = result.scalars().all()
                    if not groups:
                        logger.warning("No groups found in the database")
                        return

                    for group in groups:
                        logger.debug(f"Processing group {group.chat_id}: {group.name}")
                        hero = await GroupUserRepository.select_hero_of_the_day(
                            session, group.chat_id, today
                        )
                        if hero:
                            user = await GroupUserRepository.get_user_by_id(
                                session, hero.user_id
                            )
                            if user:
                                await send_hero_notification(
                                    bot, group.chat_id, hero, user
                                )
                            else:
                                logger.warning(
                                    f"No user found for hero ID {hero.user_id} in group {group.chat_id}"
                                )
                        else:
                            logger.info(
                                f"No hero selected for group {group.chat_id} on {today}"
                            )
                except Exception as e:
                    logger.error(f"Error processing group: {e}", exc_info=True)
                    continue  # Продолжаем с следующей группой

        # Запускаем асинхронную функцию в текущем цикле событий
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())
    except Exception as e:
        logger.error(f"Error processing hero selection: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    finally:
        if bot:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(bot.session.close())
