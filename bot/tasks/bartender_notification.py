from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_async_session
from bot.core.repositories.event_repository import EventRepository
from bot.logger import setup_logger
from aiogram import Bot
from db.models import Event
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
logger = setup_logger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


async def send_bartender_notification(bot: Bot, event: Event):
    try:
        message_text = (
            f"🍺 Новое событие '{event.name}' создано!\n"
            f"📅 Дата: {event.event_date.strftime('%d.%m.%Y')}\n"
            f"🕐 Время: {event.event_time.strftime('%H:%M')}\n"
            f"📍 Место: {event.location_name or 'Не указано'}\n"
            f"🍻 Пиво: {f'{event.beer_option_1}, {event.beer_option_2}' if event.has_beer_choice else 'Лагер'}"
        )
        await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=message_text)
        logger.info(f"Уведомление бармену отправлено для события {event.id}")
    except Exception as e:
        logger.error(
            f"Ошибка отправки уведомления бармену для события {event.id}: {e}",
            exc_info=True,
        )
        raise


@shared_task(bind=True, ignore_result=True)
def process_event_notification(self, event_id: int):
    logger.info(f"Обработка задачи уведомления для события {event_id}")
    bot = None
    loop = None
    try:
        bot = Bot(token=BOT_TOKEN)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def run():
            async for session in get_async_session():
                event = await EventRepository.get_event_by_id(session, event_id)
                if not event:
                    logger.warning(f"Событие {event_id} не найдено в базе, пропуск")
                    return
                await send_bartender_notification(bot, event)
                logger.info(f"Обработано событие {event_id}")

        loop.run_until_complete(run())
    except Exception as e:
        logger.error(
            f"Ошибка обработки уведомления для события {event_id}: {e}", exc_info=True
        )
        raise self.retry(exc=e, countdown=60)  # Повтор через 60 секунд
    finally:
        if bot:

            async def close_bot():
                await bot.session.close()

            loop.run_until_complete(close_bot())
