from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from bot.fsm.event import EventCreationStates
from bot.texts import (
    EVENT_NOT_PRIVATE,
    EVENT_NO_PERMISSION,
    EVENT_NAME_PROMPT,
    EVENT_NAME_INVALID,
    EVENT_DATE_PROMPT,
    EVENT_DATE_INVALID,
    EVENT_DATE_PAST,
    EVENT_TIME_PROMPT,
    EVENT_TIME_INVALID,
    EVENT_LOCATION_PROMPT,
    EVENT_LOCATION_INVALID,
    EVENT_LOCATION_NAME_PROMPT,
    EVENT_LOCATION_NAME_INVALID,
    EVENT_DESCRIPTION_PROMPT,
    EVENT_DESCRIPTION_INVALID,
    EVENT_IMAGE_PROMPT,
    EVENT_IMAGE_INVALID,
    EVENT_BEER_CHOICE_PROMPT,
    EVENT_BEER_OPTIONS_PROMPT,
    EVENT_BEER_INVALID,
    EVENT_NOTIFICATION_CHOICE_PROMPT,
    EVENT_NOTIFICATION_TIME_PROMPT,
    EVENT_NOTIFICATION_TIME_INVALID,
    EVENT_NOTIFICATION_TIME_PAST,
    EVENT_ERROR,
    EVENT_CANCEL_SUCCESS,
    EVENT_CREATED,
    EVENT_NOTIFICATION_TEXT,
    EVENT_NOTIFICATION_SUMMARY,
)
from db.database import async_session_maker
from db.services import get_group_admin_by_user_id, create_event, get_users_by_group_id
from db.schemas import EventCreate
from bot.logger import setup_logger
from celery_app.tasks import send_notification
from datetime import datetime
import pendulum
import re
from typing import Optional

router = Router()
logger = setup_logger("event")


def get_cancel_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить", callback_data="cancel_event_creation"
                )
            ]
        ]
    )


def get_beer_choice_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="choice_yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="choice_no")],
            [
                InlineKeyboardButton(
                    text="🚫 Отменить", callback_data="cancel_event_creation"
                )
            ],
        ]
    )


def get_notification_choice_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 Немедленно", callback_data="notify_immediate"
                )
            ],
            [InlineKeyboardButton(text="⏰ Отложенно", callback_data="notify_delayed")],
            [
                InlineKeyboardButton(
                    text="🚫 Отменить", callback_data="cancel_event_creation"
                )
            ],
        ]
    )


def get_notification_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍺 Выбрать пиво", callback_data="cmd_beer")],
            [InlineKeyboardButton(text="🏠 В начало", callback_data="cmd_start")],
        ]
    )


@router.message(Command("create_event"))
async def create_event_handler(
    message: Message, bot: Bot, state: FSMContext, session: AsyncSession
):
    if message.chat.type != "private":
        await message.answer(EVENT_NOT_PRIVATE)
        return
    admin = await get_group_admin_by_user_id(session, message.from_user.id)
    if not admin:
        await message.answer(EVENT_NO_PERMISSION)
        return
    await state.update_data(chat_id=admin.chat_id)
    await message.answer(EVENT_NAME_PROMPT, reply_markup=get_cancel_keyboard())
    await state.set_state(EventCreationStates.waiting_for_name)


@router.message(EventCreationStates.waiting_for_name)
async def process_event_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 200:
        await message.answer(EVENT_NAME_INVALID, reply_markup=get_cancel_keyboard())
        return
    await state.update_data(name=name)
    await message.answer(
        EVENT_DATE_PROMPT.format(name=name), reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EventCreationStates.waiting_for_date)


@router.message(EventCreationStates.waiting_for_date)
async def process_event_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
        await message.answer(EVENT_DATE_INVALID, reply_markup=get_cancel_keyboard())
        return
    try:
        event_date = pendulum.from_format(
            date_str, "DD.MM.YYYY", tz="Europe/Moscow"
        ).date()
        today = pendulum.now("Europe/Moscow").date()
        if event_date < today:
            await message.answer(EVENT_DATE_PAST, reply_markup=get_cancel_keyboard())
            return
        await state.update_data(event_date=date_str)
        await message.answer(
            EVENT_TIME_PROMPT.format(date=date_str),
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_time)
    except pendulum.exceptions.ParserError:
        await message.answer(EVENT_DATE_INVALID, reply_markup=get_cancel_keyboard())


@router.message(EventCreationStates.waiting_for_time)
async def process_event_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        await message.answer(EVENT_TIME_INVALID, reply_markup=get_cancel_keyboard())
        return
    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            await message.answer(EVENT_TIME_INVALID, reply_markup=get_cancel_keyboard())
            return
        await state.update_data(event_time=time_str)
        await message.answer(
            EVENT_LOCATION_PROMPT.format(time=time_str),
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_location)
    except ValueError:
        await message.answer(EVENT_TIME_INVALID, reply_markup=get_cancel_keyboard())


@router.message(EventCreationStates.waiting_for_location)
async def process_event_location(message: Message, state: FSMContext):
    input_str = message.text.strip()
    latitude = None
    longitude = None
    if input_str != "-":
        if not re.match(r"^-?\d+\.\d+,-?\d+\.\d+$", input_str):
            await message.answer(
                EVENT_LOCATION_INVALID, reply_markup=get_cancel_keyboard()
            )
            return
        try:
            lat_str, lon_str = map(str.strip, input_str.split(","))
            latitude = float(lat_str)
            longitude = float(lon_str)
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                await message.answer(
                    EVENT_LOCATION_INVALID, reply_markup=get_cancel_keyboard()
                )
                return
        except ValueError:
            await message.answer(
                EVENT_LOCATION_INVALID, reply_markup=get_cancel_keyboard()
            )
            return
    await state.update_data(latitude=latitude, longitude=longitude)
    await message.answer(EVENT_LOCATION_NAME_PROMPT, reply_markup=get_cancel_keyboard())
    await state.set_state(EventCreationStates.waiting_for_location_name)


@router.message(EventCreationStates.waiting_for_location_name)
async def process_event_location_name(message: Message, state: FSMContext):
    input_str = message.text.strip()
    location_name = None
    if input_str != "-":
        if not input_str or len(input_str) > 500:
            await message.answer(
                EVENT_LOCATION_NAME_INVALID, reply_markup=get_cancel_keyboard()
            )
            return
        location_name = input_str
    await state.update_data(location_name=location_name)
    await message.answer(
        EVENT_DESCRIPTION_PROMPT.format(location=location_name or "Не указано"),
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(EventCreationStates.waiting_for_description)


@router.message(EventCreationStates.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext):
    input_str = message.text.strip()
    description = None
    if input_str != "-":
        if not input_str or len(input_str) > 1000:
            await message.answer(
                EVENT_DESCRIPTION_INVALID, reply_markup=get_cancel_keyboard()
            )
            return
        description = input_str
    await state.update_data(description=description)
    await message.answer(
        EVENT_IMAGE_PROMPT.format(description=description or "Не указано"),
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(EventCreationStates.waiting_for_image)


@router.message(EventCreationStates.waiting_for_image)
async def process_event_image(message: Message, state: FSMContext):
    image_file_id = None
    if message.text and message.text.strip() == "-":
        pass
    elif message.photo:
        image_file_id = message.photo[-1].file_id
    else:
        await message.answer(EVENT_IMAGE_INVALID, reply_markup=get_cancel_keyboard())
        return
    await state.update_data(image_file_id=image_file_id)
    await message.answer(
        EVENT_BEER_CHOICE_PROMPT.format(
            image="Загружено" if image_file_id else "Не загружено"
        ),
        reply_markup=get_beer_choice_keyboard(),
    )
    await state.set_state(EventCreationStates.waiting_for_beer_choice)


@router.callback_query(lambda c: c.data in ["choice_yes", "choice_no"])
async def process_beer_choice(
    callback_query: CallbackQuery, bot: Bot, state: FSMContext
):
    await callback_query.answer()
    has_beer_choice = callback_query.data == "choice_yes"
    await state.update_data(has_beer_choice=has_beer_choice)
    if has_beer_choice:
        await bot.edit_message_text(
            EVENT_BEER_OPTIONS_PROMPT,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_beer_options)
    else:
        await state.update_data(beer_option_1="Лагер", beer_option_2=None)
        await bot.edit_message_text(
            EVENT_NOTIFICATION_CHOICE_PROMPT,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=get_notification_choice_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_notification_choice)


@router.message(EventCreationStates.waiting_for_beer_options)
async def process_beer_options(message: Message, state: FSMContext, bot: Bot):
    input_str = message.text.strip()
    if not re.match(r"[^,]+,[^,]+", input_str):
        await message.answer(
            EVENT_BEER_OPTIONS_INVALID, reply_markup=get_cancel_keyboard()
        )
        return
    beer_options = [option.strip() for option in input_str.split(",")]
    if len(beer_options) != 2 or not all(
        1 <= len(option) <= 100 for option in beer_options
    ):
        await message.answer(EVENT_BEER_INVALID, reply_markup=get_cancel_keyboard())
        return
    await state.update_data(
        beer_option_1=beer_options[0], beer_option_2=beer_options[1]
    )
    await message.answer(
        EVENT_NOTIFICATION_CHOICE_PROMPT,
        reply_markup=get_notification_choice_keyboard(),
    )
    await state.set_state(EventCreationStates.waiting_for_notification_choice)


@router.callback_query(lambda c: c.data in ["notify_immediate", "notify_delayed"])
async def process_notification_choice(
    callback_query: CallbackQuery, bot: Bot, state: FSMContext
):
    await callback_query.answer()
    notification_choice = callback_query.data
    await state.update_data(notification_choice=notification_choice)
    if notification_choice == "notify_immediate":
        await finalize_event_creation(callback_query.message, bot, state)
    else:
        await bot.edit_message_text(
            EVENT_NOTIFICATION_TIME_PROMPT,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_notification_time)


@router.message(EventCreationStates.waiting_for_notification_time)
async def process_notification_time(message: Message, state: FSMContext, bot: Bot):
    time_str = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        await message.answer(
            EVENT_NOTIFICATION_TIME_INVALID, reply_markup=get_cancel_keyboard()
        )
        return
    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            await message.answer(
                EVENT_NOTIFICATION_TIME_INVALID, reply_markup=get_cancel_keyboard()
            )
            return
        data = await state.get_data()
        event_date = pendulum.from_format(
            data["event_date"], "DD.MM.YYYY", tz="Europe/Moscow"
        ).date()
        notification_datetime = pendulum.datetime(
            year=event_date.year,
            month=event_date.month,
            day=event_date.day,
            hour=hour,
            minute=minute,
            tz="Europe/Moscow",
        )
        now = pendulum.now("Europe/Moscow")
        if notification_datetime < now:
            await message.answer(
                EVENT_NOTIFICATION_TIME_PAST, reply_markup=get_cancel_keyboard()
            )
            return
        await state.update_data(notification_time=time_str)
        await finalize_event_creation(message, bot, state)
    except ValueError:
        await message.answer(
            EVENT_NOTIFICATION_TIME_INVALID, reply_markup=get_cancel_keyboard()
        )


async def finalize_event_creation(message: Message, bot: Bot, state: FSMContext):
    try:
        data = await state.get_data()
        has_beer_choice = data.get("has_beer_choice", False)
        beer_option_1 = data.get("beer_option_1")
        beer_option_2 = data.get("beer_option_2")
        if has_beer_choice and (not beer_option_1 or not beer_option_2):
            await message.answer(EVENT_BEER_INVALID, reply_markup=get_cancel_keyboard())
            return
        event_date = pendulum.from_format(
            data["event_date"], "DD.MM.YYYY", tz="Europe/Moscow"
        ).date()
        event_time = datetime.strptime(data["event_time"], "%H:%M").time()
        event_data = EventCreate(
            name=data["name"],
            event_date=event_date,
            event_time=event_time,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            location_name=data.get("location_name"),
            description=data.get("description"),
            image_file_id=data.get("image_file_id"),
            has_beer_choice=has_beer_choice,
            beer_option_1=beer_option_1,
            beer_option_2=beer_option_2,
            created_by=message.from_user.id,
            chat_id=data["chat_id"],
        )
        async with async_session_maker() as session:
            event = await create_event(session, event_data)
            event_start = pendulum.datetime(
                year=event.event_date.year,
                month=event.event_date.month,
                day=event.event_date.day,
                hour=event.event_time.hour,
                minute=event.event_time.minute,
                tz="Europe/Moscow",
            )
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
            notification_choice = data.get("notification_choice", "notify_immediate")
            if notification_choice == "notify_immediate":
                await send_event_notifications(bot, event, session, notification_text)
            else:
                notification_time = data["notification_time"]
                hour, minute = map(int, notification_time.split(":"))
                eta = datetime(
                    year=event_date.year,
                    month=event_date.month,
                    day=event_date.day,
                    hour=hour,
                    minute=minute,
                    tzinfo=pendulum.timezone("Europe/Moscow"),
                )
                try:
                    task = send_notification.apply_async(
                        args=[event.id, notification_text],
                        eta=eta,
                    )
                    logger.info(
                        f"Scheduled notification task {task.id} for event {event.id} at {eta}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to schedule notification task for event {event.id}: {e}",
                        exc_info=True,
                    )
                    await message.answer(
                        "⚠️ Событие создано, но уведомление не запланировано. Свяжитесь с администратором.",
                        reply_markup=get_cancel_keyboard(),
                    )
                    await state.clear()
                    return
            # Schedule bartender notification at event start time
            try:
                eta = datetime(
                    year=event_start.year,
                    month=event_start.month,
                    day=event_start.day,
                    hour=event_start.hour,
                    minute=event_start.minute,
                    tzinfo=event_start.tzinfo,
                )
                task = send_notification.apply_async(
                    args=[event.id, notification_text],
                    eta=eta,
                )
                logger.info(
                    f"Scheduled bartender notification task {task.id} for event {event.id} at {eta}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to schedule bartender notification task for event {event.id}: {e}",
                    exc_info=True,
                )
                await message.answer(
                    "⚠️ Событие создано, но уведомление бармену не запланировано. Свяжитесь с администратором.",
                    reply_markup=get_cancel_keyboard(),
                )
                await state.clear()
                return
            summary = EVENT_NOTIFICATION_SUMMARY.format(
                name=event.name,
                date=event.event_date.strftime("%d.%m.%Y"),
                time=event.event_time.strftime("%H:%M"),
                location=event.location_name or "Не указано",
                description=event.description or "Не указано",
                image="Есть" if event.image_file_id else "Нет",
                beer_choice="Да" if event.has_beer_choice else "Нет",
                beer_options=(
                    f"{event.beer_option_1}, {event.beer_option_2}"
                    if event.has_beer_choice
                    else "Лагер"
                ),
            )
            await message.answer(summary)
            await message.answer(EVENT_CREATED)
            logger.info(f"Event created: {event.id} by {message.from_user.id}")
        await state.clear()
    except Exception as e:
        logger.error(f"Error finalizing event creation: {e}", exc_info=True)
        await message.answer(EVENT_ERROR, reply_markup=get_cancel_keyboard())
        await state.clear()


async def send_event_notifications(
    bot: Bot, event, session: AsyncSession, notification_text: str
):
    users = await get_users_by_group_id(session, event.chat_id)
    successful_sends = 0
    failed_sends = 0
    for user in users:
        try:
            if event.image_file_id:
                await bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=event.image_file_id,
                    caption=notification_text,
                    reply_markup=get_notification_keyboard(),
                )
            else:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=notification_text,
                    reply_markup=get_notification_keyboard(),
                )
            successful_sends += 1
        except TelegramAPIError as e:
            logger.warning(
                f"Failed to send notification to user {user.telegram_id}: {e}"
            )
            failed_sends += 1
    logger.info(
        f"Event notifications sent: {successful_sends} successful, {failed_sends} failed"
    )


@router.callback_query(lambda c: c.data == "cancel_event_creation")
async def cancel_event_creation(
    callback_query: CallbackQuery, bot: Bot, state: FSMContext
):
    await callback_query.answer()
    await bot.edit_message_text(
        EVENT_CANCEL_SUCCESS,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
    )
    await state.clear()
