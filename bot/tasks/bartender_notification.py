import os
import asyncio
from celery import shared_task
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.event_repository import EventRepository
from bot.core.repositories.beer_repository import BeerRepository
from bot.texts import BARTENDER_NOTIFICATION
from bot.logger import setup_logger
from db.database import get_async_session_context
from db.models import Event

logger = setup_logger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


async def send_bartender_notification(bot: Bot, event: Event, session: AsyncSession):
    stats = await BeerRepository.get_event_beer_orders(session, event.id)
    participants = stats["participants"]
    beer_orders = stats["beer_orders"]
    beer_orders_str = ""
    if event.has_beer_choice and event.beer_option_1 and event.beer_option_2:
        beer_orders_str += (
            f"🍻 {event.beer_option_1}: {beer_orders.get(event.beer_option_1, 0)}\n"
        )
        beer_orders_str += (
            f"🍻 {event.beer_option_2}: {beer_orders.get(event.beer_option_2, 0)}"
        )
    else:
        beer_orders_str += f"🍻 Лагер: {beer_orders.get('Лагер', participants)}"
    event_date = event.event_date.strftime("%d.%m.%Y")
    event_time = event.event_time.strftime("%H:%M")
    message_text = BARTENDER_NOTIFICATION.format(
        name=event.name,
        date=event_date,
        time=event_time,
        participants=participants,
        beer_orders=beer_orders_str,
    )
    await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=message_text)
    logger.info(
        f"Уведомление бармену отправлено для события {event.id}: {message_text}"
    )


@shared_task(bind=True, ignore_result=True)
def process_event_notification(self, event_id: int):
    logger.info(f"Processing notification task for event {event_id}")
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
                event = await EventRepository.get_event_by_id(session, event_id)
                if not event:
                    logger.warning(f"Событие {event_id} не найдено")
                    return
                await send_bartender_notification(bot, event, session)
        except Exception as e:
            logger.error(
                f"Ошибка в задаче уведомления для события {event_id}: {e}",
                exc_info=True,
            )
            raise self.retry(exc=e, countdown=60, max_retries=3)
        finally:
            await bot.session.close()

    try:
        loop.run_until_complete(main())
    finally:
        if not loop.is_closed():
            loop.close()
