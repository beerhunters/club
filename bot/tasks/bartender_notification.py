import os
import asyncio
from celery import shared_task
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.event_repository import EventRepository
from bot.core.repositories.user_repository import UserRepository
from bot.core.repositories.beer_repository import BeerRepository
from bot.texts import BARTENDER_NOTIFICATION, EVENT_NOTIFICATION_TEXT
from bot.logger import setup_logger
from db.database import get_async_session_context
from aiogram.exceptions import TelegramAPIError
from db.models import Event

logger = setup_logger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


def get_command_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🍺 Выбрать пиво", callback_data="cmd_beer")
    )
    builder.add(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    builder.adjust(2)
    return builder.as_markup()


async def send_bartender_notification(bot: Bot, event: Event, session: AsyncSession):
    stats = await BeerRepository.get_event_beer_orders(session, event.id)
    participants = stats["participants"]
    beer_orders = stats["beer_orders"]
    beer_orders_str = ""
    if beer_orders:
        beer_orders_str = "\n".join(
            f"{beer}: {count}" for beer, count in beer_orders.items()
        )
    event_date = event.event_date.strftime("%d.%m.%Y")
    event_time = event.event_time.strftime("%H:%M")
    message_text = BARTENDER_NOTIFICATION.format(
        name=event.name,
        date=event_date,
        time=event_time,
        participants=participants,
        beer_orders=beer_orders_str,
    )
    try:
        await bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID, text=message_text, parse_mode="HTML"
        )
        logger.info(f"Уведомление бармену отправлено для события {event.id}")
    except Exception as e:
        logger.error(
            f"Ошибка отправки уведомления бармену для события {event.id}: {e}",
            exc_info=True,
        )


async def send_event_notifications(bot: Bot, event: Event, session: AsyncSession):
    users = await UserRepository.get_all_users(session, limit=1000)
    notification_text = EVENT_NOTIFICATION_TEXT.format(
        name=event.name,
        date=event.event_date.strftime("%d.%m.%Y"),
        time=event.event_time.strftime("%H:%M"),
        location=event.location_name or "Не указано",
        description=event.description or "Не указано",
        beer_options=(
            f"{event.beer_option_1}, {event.beer_option_2}"
            if event.has_beer_choice
            else "Лагер"
        ),
    )
    successful_sends = 0
    failed_sends = 0
    for user in users:
        try:
            if event.image_file_id:
                await bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=event.image_file_id,
                    caption=notification_text,
                    reply_markup=get_command_keyboard(),
                )
            else:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=notification_text,
                    reply_markup=get_command_keyboard(),
                )
            successful_sends += 1
        except TelegramAPIError as e:
            logger.warning(
                f"Failed to send notification to user {user.telegram_id}: {e}"
            )
            failed_sends += 1
        except Exception as e:
            logger.error(
                f"Unexpected error sending notification to user {user.telegram_id}: {e}"
            )
            failed_sends += 1
    logger.info(
        f"Event notifications sent: {successful_sends} successful, {failed_sends} failed"
    )


@shared_task(bind=True, ignore_result=True)
def process_user_notification(self, event_id: int):
    logger.info(f"Запуск задачи уведомления пользователей для события {event_id}")
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
                    logger.error(f"Событие {event_id} не найдено")
                    return
                await send_event_notifications(bot, event, session)
        except Exception as e:
            logger.error(
                f"Ошибка в задаче уведомления пользователей для события {event_id}: {e}",
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


@shared_task(bind=True, ignore_result=True)
def process_bartender_notification(self, event_id: int):
    logger.info(f"Запуск задачи уведомления бармена для события {event_id}")
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
                    logger.error(f"Событие {event_id} не найдено")
                    return
                await send_bartender_notification(bot, event, session)
        except Exception as e:
            logger.error(
                f"Ошибка в задаче уведомления бармена для события {event_id}: {e}",
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
