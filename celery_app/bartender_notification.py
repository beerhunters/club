from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.database import get_async_session
from bot.repositories.event_repo import EventRepository
from bot.repositories.beer_repo import BeerRepository
from bot.repositories.event_participant_repo import EventParticipantRepository
from db.services import get_users_by_group_id
from bot.utils.logger import setup_logger
from aiogram import Bot
from bot.core.models import Event
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date
import pendulum
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
logger = setup_logger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "267863612"))


def get_notification_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍺 Выбрать пиво", callback_data="cmd_beer")],
            [InlineKeyboardButton(text="🏠 В начало", callback_data="cmd_start")],
        ]
    )


async def count_beer_choices(
    session: AsyncSession, event: Event, today: date
) -> tuple[int, dict[str, int]]:
    try:
        event_start = pendulum.datetime(
            year=today.year,
            month=today.month,
            day=today.day,
            hour=event.event_time.hour,
            minute=event.event_time.minute,
            tz="Europe/Moscow",
        )
        window_start = event_start.subtract(minutes=30)
        logger.debug(
            f"Counting beer choices for event {event.id}: window_start={window_start}, event_start={event_start}"
        )
        beer_choices = await BeerRepository.get_choices_for_event(
            session, event, window_start, event_start
        )
        logger.debug(f"Found {len(beer_choices)} beer choices for event {event.id}")
        participant_count = len(set(choice.user_id for choice in beer_choices))
        beer_counts = {}
        valid_options = (
            [event.beer_option_1, event.beer_option_2]
            if event.has_beer_choice and event.beer_option_1 and event.beer_option_2
            else [event.beer_option_1 or "Лагер"]
        )
        valid_options = [opt for opt in valid_options if opt]
        for option in valid_options:
            beer_counts[option] = sum(
                1 for choice in beer_choices if choice.beer_choice == option
            )
        return participant_count, beer_counts
    except Exception as e:
        logger.error(
            f"Error counting beer choices for event {event.id}: {e}", exc_info=True
        )
        raise


async def send_bartender_notification(
    bot: Bot, event: Event, participant_count: int, beer_counts: dict[str, int]
):
    try:
        message_text = (
            f"🍺 Заказы на событие '{event.name}' "
            f"({event.event_date.strftime('%d.%m.%Y')} @ {event.event_time.strftime('%H:%M')}):\n"
        )
        message_text += f"👥 Участников: {participant_count}\n"
        if participant_count == 0:
            message_text += "🍻 Нет заказов."
        else:
            for beer, count in beer_counts.items():
                message_text += f"🍻 {beer}: {count}\n"
        await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=message_text)
        logger.info(
            f"Bartender notification sent for event {event.id}: {participant_count} participants"
        )
    except Exception as e:
        logger.error(
            f"Error sending bartender notification for event {event.id}: {e}",
            exc_info=True,
        )
        raise


@shared_task(bind=True, ignore_result=True)
def process_event_notification(self, event_id: int):
    logger.info(f"Processing bartender notification task for event {event_id}")
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
                    logger.warning(f"Event {event_id} not found in database, skipping")
                    return
                participant_record = (
                    await EventParticipantRepository.get_participant_record(
                        session, event_id
                    )
                )
                if participant_record:
                    logger.debug(f"Event {event_id} already processed, skipping")
                    return
                participant_count, beer_counts = await count_beer_choices(
                    session, event, event.event_date
                )
                await send_bartender_notification(
                    bot, event, participant_count, beer_counts
                )
                await EventParticipantRepository.create_participant_record(
                    session, event_id, participant_count
                )
                logger.info(
                    f"Processed event {event_id}: {participant_count} participants"
                )

        loop.run_until_complete(run())
    except Exception as e:
        logger.error(
            f"Error processing bartender notification for event {event_id}: {e}",
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=60)
    finally:
        if bot:

            async def close_bot():
                await bot.session.close()

            loop.run_until_complete(close_bot())


@shared_task(bind=True, ignore_result=True)
def send_notification(self, event_id: int, message_text: str):
    logger.info(f"Processing user notification task for event {event_id}")
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
                    logger.warning(f"Event {event_id} not found in database, skipping")
                    return
                users = await get_users_by_group_id(session, event.chat_id)
                successful_sends = 0
                failed_sends = 0
                for user in users:
                    try:
                        if event.image_file_id:
                            await bot.send_photo(
                                chat_id=user.telegram_id,
                                photo=event.image_file_id,
                                caption=message_text,
                                reply_markup=get_notification_keyboard(),
                            )
                        else:
                            await bot.send_message(
                                chat_id=user.telegram_id,
                                text=message_text,
                                reply_markup=get_notification_keyboard(),
                            )
                        successful_sends += 1
                    except TelegramAPIError as e:
                        logger.warning(
                            f"Failed to send notification to user {user.telegram_id}: {e}"
                        )
                        failed_sends += 1
                logger.info(
                    f"User notifications sent for event {event_id}: {successful_sends} successful, {failed_sends} failed"
                )

        loop.run_until_complete(run())
    except Exception as e:
        logger.error(
            f"Error processing user notification for event {event_id}: {e}",
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=60)
    finally:
        if bot:

            async def close_bot():
                await bot.session.close()

            loop.run_until_complete(close_bot())
