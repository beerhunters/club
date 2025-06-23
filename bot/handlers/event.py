from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, time
import pendulum

from bot.fsm.event import EventCreationStates
from db.services import create_event, get_users_by_group_id, get_group_admin_by_user_id
from db.schemas import EventCreate
from bot.texts import (
    EVENT_NOTIFICATION_TEXT,
    EVENT_NOTIFICATION_SUMMARY,
    EVENT_CREATED,
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
    EVENT_BEER_OPTIONS_INVALID,
    EVENT_NOTIFICATION_CHOICE_PROMPT,
    EVENT_NOTIFICATION_TIME_PROMPT,
    EVENT_NOTIFICATION_TIME_INVALID,
    EVENT_NOTIFICATION_TIME_PAST,
    EVENT_NO_PERMISSION,
    EVENT_NAME_PROMPT,
)
from bot.logger import setup_logger
from bot.tasks.event_notification import send_notification
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()
logger = setup_logger("event")


def get_cancel_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )


def get_beer_choice_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="choice_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="choice_no"),
            ]
        ]
    )


def get_notification_choice_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 Уведомить", callback_data="notify_immediate"
                ),
                InlineKeyboardButton(
                    text="🔕 Без уведомления", callback_data="no_notification"
                ),
            ]
        ]
    )


def get_notification_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )


@router.message(Command("event"))
async def cmd_event(message: Message, session: AsyncSession, state: FSMContext):
    admin = await get_group_admin_by_user_id(session, message.from_user.id)
    if not admin:
        await message.answer(EVENT_NO_PERMISSION)
        return
    await message.answer(EVENT_NAME_PROMPT, reply_markup=get_cancel_keyboard())
    await state.set_state(EventCreationStates.waiting_for_name)


@router.message(EventCreationStates.waiting_for_name)
async def process_event_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 1 or len(name) > 255:
        await message.answer(EVENT_NAME_INVALID, reply_markup=get_cancel_keyboard())
        return
    await state.update_data(event_name=name)
    await message.answer(
        EVENT_DATE_PROMPT.format(name=name), reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EventCreationStates.waiting_for_date)


@router.message(EventCreationStates.waiting_for_date)
async def process_event_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    try:
        event_date = pendulum.from_format(date_str, "DD.MM.YYYY").date()
        today = pendulum.now("Europe/Moscow").date()
        if event_date < today:
            await message.answer(EVENT_DATE_PAST, reply_markup=get_cancel_keyboard())
            return
    except ValueError:
        await message.answer(EVENT_DATE_INVALID, reply_markup=get_cancel_keyboard())
        return
    await state.update_data(event_date=event_date)
    await message.answer(EVENT_TIME_PROMPT, reply_markup=get_cancel_keyboard())
    await state.set_state(EventCreationStates.waiting_for_time)


@router.message(EventCreationStates.waiting_for_time)
async def process_event_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    try:
        event_time = time.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer(EVENT_TIME_INVALID, reply_markup=get_cancel_keyboard())
        return
    await state.update_data(event_time=time_str)
    await message.answer(
        EVENT_LOCATION_PROMPT.format(time=time_str), reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EventCreationStates.waiting_for_location)


@router.message(EventCreationStates.waiting_for_location)
async def process_event_location(message: Message, state: FSMContext):
    input_str = message.text.strip()
    latitude = None
    longitude = None
    if input_str != "-":
        try:
            lat_str, lon_str = input_str.split(",")
            latitude = float(lat_str)
            longitude = float(lon_str)
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError
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
    location_name = None
    input_str = message.text.strip()
    if input_str != "-":
        location_name = input_str
        if len(location_name) < 1 or len(location_name) > 500:
            await message.answer(
                EVENT_LOCATION_NAME_INVALID, reply_markup=get_cancel_keyboard()
            )
            return
    await state.update_data(location_name=location_name)
    await message.answer(
        EVENT_DESCRIPTION_PROMPT.format(location=location_name or "Не указано"),
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(EventCreationStates.waiting_for_description)


@router.message(EventCreationStates.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext):
    description = None
    input_str = message.text.strip()
    if input_str != "-":
        description = input_str
        if len(description) < 1 or len(description) > 1000:
            await message.answer(
                EVENT_DESCRIPTION_INVALID, reply_markup=get_cancel_keyboard()
            )
            return
    await state.update_data(description=description)
    await message.answer(
        EVENT_IMAGE_PROMPT.format(description=description or "Не указано"),
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(EventCreationStates.waiting_for_image)


@router.message(EventCreationStates.waiting_for_image)
async def process_event_image(message: Message, state: FSMContext):
    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif message.text.strip() != "-":
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


@router.callback_query(lambda c: c.data.startswith("choice_"))
async def process_beer_choice(callback_query: CallbackQuery, state: FSMContext):
    has_beer_choice = callback_query.data == "choice_yes"
    await state.update_data(has_beer_choice=has_beer_choice)
    if has_beer_choice:
        await callback_query.message.answer(
            EVENT_BEER_OPTIONS_PROMPT, reply_markup=get_cancel_keyboard()
        )
        await state.set_state(EventCreationStates.waiting_for_beer_options)
    else:
        await callback_query.message.answer(
            EVENT_NOTIFICATION_CHOICE_PROMPT,
            reply_markup=get_notification_choice_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_notification_choice)


@router.message(EventCreationStates.waiting_for_beer_options)
async def process_beer_options(message: Message, state: FSMContext, bot: Bot):
    input_str = message.text.strip()
    try:
        beer_options = [option.strip() for option in input_str.split(",")]
        if len(beer_options) != 2 or any(
            len(opt) < 1 or len(opt) > 100 for opt in beer_options
        ):
            await message.answer(
                EVENT_BEER_OPTIONS_INVALID, reply_markup=get_cancel_keyboard()
            )
            return
        await state.update_data(
            beer_option_1=beer_options[0], beer_option_2=beer_options[1]
        )
    except ValueError:
        await message.answer(
            EVENT_BEER_OPTIONS_INVALID, reply_markup=get_cancel_keyboard()
        )
        return
    await message.answer(
        EVENT_NOTIFICATION_CHOICE_PROMPT,
        reply_markup=get_notification_choice_keyboard(),
    )
    await state.set_state(EventCreationStates.waiting_for_notification_choice)


@router.callback_query(lambda c: c.data in ["notify_immediate", "no_notification"])
async def process_notification_choice(
    callback_query: CallbackQuery, state: FSMContext, bot: Bot
):
    notification_choice = callback_query.data
    await state.update_data(notification_choice=notification_choice)
    if notification_choice == "notify_immediate":
        await finalize_event_creation(callback_query.message, bot, state)
    else:
        await callback_query.message.answer(
            EVENT_NOTIFICATION_TIME_PROMPT, reply_markup=get_notification_keyboard()
        )
        await state.set_state(EventCreationStates.waiting_for_notification_time)


@router.message(EventCreationStates.waiting_for_notification_time)
async def process_notification_time(message: Message, state: FSMContext, bot: Bot):
    time_str = message.text.strip()
    try:
        notification_time = pendulum.parse(time_str, tz="Europe/Moscow")
        now = pendulum.now("Europe/Moscow")
        if notification_time <= now:
            await message.answer(
                EVENT_NOTIFICATION_TIME_PAST, reply_markup=get_notification_keyboard()
            )
            return
    except ValueError:
        await message.answer(
            EVENT_NOTIFICATION_TIME_INVALID, reply_markup=get_notification_keyboard()
        )
        return
    await state.update_data(notification_time=notification_time)
    await finalize_event_creation(message, bot, state)


async def finalize_event_creation(message: Message, bot: Bot, state: FSMContext):
    session = message.session
    data = await state.get_data()
    event_time = datetime.strptime(data["event_time"], "%H:%M").time()
    event_date = pendulum.parse(data["event_date"]).date()
    event_data = EventCreate(
        name=data["event_name"],
        event_date=event_date,
        event_time=event_time,
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        location_name=data.get("location_name"),
        description=data.get("description"),
        image_file_id=data.get("image_file_id"),
        has_beer_choice=data.get("has_beer_choice", False),
        beer_option_1=data.get("beer_option_1"),
        beer_option_2=data.get("beer_option_2"),
        created_by=message.from_user.id,
        chat_id=message.chat.id,
        celery_task_id=None,
    )
    event = await create_event(session, event_data)
    beer_options = "Лагер"
    if event_data.has_beer_choice:
        beer_options = f"{data['beer_option_1']}, {data['beer_option_2']}"
    notification_choice = data.get("notification_choice", "notify_immediate")
    notification_text = EVENT_NOTIFICATION_TEXT.format(
        name=event_data.name,
        date=event_data.event_date,
        time=event_data.event_time,
        location=event_data.location_name or "Не указано",
        description=event_data.description or "Не указано",
        beer_options=beer_options,
    )
    if notification_choice == "notify_immediate":
        task = send_notification.delay(event.chat_id, notification_text)
        event.celery_task_id = task.id
        await session.commit()
    elif data.get("notification_time"):
        notification_time = data["notification_time"]
        eta = notification_time.to_datetime_string()
        task = send_notification.apply_async(
            args=[event.chat_id, notification_text],
            eta=notification_time,
        )
        event.celery_task_id = task.id
        await session.commit()
    summary = EVENT_NOTIFICATION_SUMMARY.format(
        name=event_data.name,
        date=event_data.event_date,
        time=event_data.event_time,
        location=event_data.location_name or "Не указано",
        description=event_data.description or "Не указано",
        image="Загружено" if event_data.image_file_id else "Не загружено",
        beer_choice="Да" if event_data.has_beer_choice else "Нет",
        beer_options=beer_options,
    )
    users = await get_users_by_group_id(session, event.chat_id)
    successful_sends = 0
    failed_sends = 0
    if notification_choice == "notify_immediate":
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=notification_text,
                    reply_markup=None,
                )
                successful_sends += 1
            except Exception as e:
                logger.error(f"Failed to send notification to {user.telegram_id}: {e}")
                failed_sends += 1
    await message.answer(f"{EVENT_CREATED}\n\n{summary}")
    await state.clear()
