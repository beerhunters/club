from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.event_repository import EventRepository
from bot.core.repositories.group_admin_repository import GroupAdminRepository
from bot.core.repositories.user_repository import UserRepository
from bot.fsm.event import EventCreationStates
from db.database import get_async_session_context
from db.schemas import EventCreate
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
    EVENT_BEER_OPTIONS_INVALID,
    EVENT_NOTIFICATION_SUMMARY,
    EVENT_CREATED,
    EVENT_ERROR,
    EVENT_CANCEL_SUCCESS,
    EVENT_NOTIFICATION_TEXT,
    EVENT_NOTIFICATION_CHOICE_PROMPT,
    EVENT_NOTIFICATION_TIME_PROMPT,
    EVENT_NOTIFICATION_TIME_INVALID,
    EVENT_NOTIFICATION_TIME_PAST,
    EVENT_NOTIFICATION_SCHEDULED,
    EVENT_NOTIFICATION_TIME_PROMPT_SCHEDULED,
    EVENT_NOTIFICATION_TIME_INVALID_SCHEDULED,
    EVENT_NOTIFICATION_TIME_PAST_SCHEDULED,
)
from shared.decorators import private_chat_only
from bot.logger import setup_logger
from bot.tasks.celery_app import app as celery_app
from sqlalchemy import update
from db.models import Event
import pendulum
import re
from datetime import time, datetime
from typing import Optional
from sqlalchemy.exc import IntegrityError, ProgrammingError
from aiogram.exceptions import TelegramAPIError

logger = setup_logger(__name__)
router = Router()


def get_cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(
            text="❌ Отменить", callback_data="cancel_event_creation"
        )
    )
    return builder.as_markup()


def get_beer_choice_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="✅ Да", callback_data="choice_yes"))
    builder.add(types.InlineKeyboardButton(text="❌ Нет", callback_data="choice_no"))
    builder.add(
        types.InlineKeyboardButton(
            text="🚫 Отменить", callback_data="cancel_event_creation"
        )
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def get_command_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🍺 Выбрать пиво", callback_data="cmd_beer")
    )
    builder.add(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    builder.adjust(2)
    return builder.as_markup()


def get_notification_choice_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Уведомить сейчас", callback_data="notify_now")
    builder.button(text="Отложенный пост", callback_data="notify_later")
    builder.button(text="Отмена", callback_data="cancel_event_creation")
    builder.adjust(2)
    return builder.as_markup()


@router.message(Command("create_event"))
@private_chat_only(response_probability=0.5)
async def create_event_handler(
    message: types.Message, bot: Bot, state: FSMContext, session: AsyncSession
):
    try:
        user_id = message.from_user.id
        admin_chat_id = await GroupAdminRepository.get_admin_chat_id(session, user_id)
        if not admin_chat_id:
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_NO_PERMISSION,
            )
            return
        await state.update_data(admin_chat_id=admin_chat_id, user_id=user_id)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_NAME_PROMPT,
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_name)
    except Exception as e:
        logger.error(f"Error in create_event handler: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_name)
@private_chat_only(response_probability=0.5)
async def process_event_name(message: types.Message, bot: Bot, state: FSMContext):
    try:
        name = message.text.strip()
        if not name or len(name) > 255:
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_NAME_INVALID,
                reply_markup=get_cancel_keyboard(),
            )
            return
        await state.update_data(name=name)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_DATE_PROMPT.format(name=name),
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_date)
    except Exception as e:
        logger.error(f"Error processing event name: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_date)
@private_chat_only(response_probability=0.5)
async def process_event_date(message: types.Message, bot: Bot, state: FSMContext):
    try:
        date_str = message.text.strip()
        if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_DATE_INVALID,
                reply_markup=get_cancel_keyboard(),
            )
            return
        event_date = pendulum.from_format(
            date_str, "DD.MM.YYYY", tz="Europe/Moscow"
        ).date()
        today = pendulum.now("Europe/Moscow").date()
        if event_date < today:
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_DATE_PAST,
                reply_markup=get_cancel_keyboard(),
            )
            return
        await state.update_data(event_date=event_date.to_date_string())
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_TIME_PROMPT.format(date=event_date.strftime("%d.%m.%Y")),
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_time)
    except pendulum.exceptions.ParserError:
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_DATE_INVALID,
            reply_markup=get_cancel_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error processing event date: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_time)
@private_chat_only(response_probability=0.5)
async def process_event_time(message: types.Message, bot: Bot, state: FSMContext):
    try:
        time_str = message.text.strip()
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_TIME_INVALID,
                reply_markup=get_cancel_keyboard(),
            )
            return
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_TIME_INVALID,
                reply_markup=get_cancel_keyboard(),
            )
            return
        event_time = time(hour=hour, minute=minute)
        await state.update_data(event_time=event_time.strftime("%H:%M"))
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_LOCATION_PROMPT.format(time=event_time.strftime("%H:%M")),
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_location)
    except ValueError:
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_TIME_INVALID,
            reply_markup=get_cancel_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error processing event time: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_location)
@private_chat_only(response_probability=0.5)
async def process_event_location(message: types.Message, bot: Bot, state: FSMContext):
    try:
        input_str = message.text.strip()
        latitude = None
        longitude = None
        if input_str != "-":
            if not re.match(r"^-?\d+\.\d+,-?\d+\.\d+$", input_str):
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=EVENT_LOCATION_INVALID,
                    reply_markup=get_cancel_keyboard(),
                )
                return
            lat_str, lon_str = map(str.strip, input_str.split(","))
            try:
                latitude = float(lat_str)
                longitude = float(lon_str)
                if not (-90 <= latitude <= 90):
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=EVENT_LOCATION_INVALID,
                        reply_markup=get_cancel_keyboard(),
                    )
                    return
                if not (-180 <= longitude <= 180):
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=EVENT_LOCATION_INVALID,
                        reply_markup=get_cancel_keyboard(),
                    )
                    return
            except ValueError:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=EVENT_LOCATION_INVALID,
                    reply_markup=get_cancel_keyboard(),
                )
                return
        await state.update_data(latitude=latitude, longitude=longitude)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_LOCATION_NAME_PROMPT,
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_location_name)
    except Exception as e:
        logger.error(f"Error processing event location: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_location_name)
@private_chat_only(response_probability=0.5)
async def process_event_location_name(
    message: types.Message, bot: Bot, state: FSMContext
):
    try:
        location_name = None
        input_str = message.text.strip()
        if input_str != "-":
            if not input_str or len(input_str) > 500:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=EVENT_LOCATION_NAME_INVALID,
                    reply_markup=get_cancel_keyboard(),
                )
                return
            location_name = input_str
        await state.update_data(location_name=location_name)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_DESCRIPTION_PROMPT.format(
                location=location_name or "Не указано"
            ),
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_description)
    except Exception as e:
        logger.error(f"Error processing event location name: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_description)
@private_chat_only(response_probability=0.5)
async def process_event_description(
    message: types.Message, bot: Bot, state: FSMContext
):
    try:
        description = None
        input_str = message.text.strip()
        if input_str != "-":
            if not input_str or len(input_str) > 1000:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=EVENT_DESCRIPTION_INVALID,
                    reply_markup=get_cancel_keyboard(),
                )
                return
            description = input_str
        await state.update_data(description=description)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_IMAGE_PROMPT.format(description=description or "Не указано"),
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_image)
    except Exception as e:
        logger.error(f"Error processing event description: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_image)
@private_chat_only(response_probability=0.5)
async def process_event_image(message: types.Message, bot: Bot, state: FSMContext):
    try:
        image_file_id = None
        if message.text and message.text.strip() == "-":
            pass
        elif message.photo:
            image_file_id = message.photo[-1].file_id
        else:
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_IMAGE_INVALID,
                reply_markup=get_cancel_keyboard(),
            )
            return
        await state.update_data(image_file_id=image_file_id)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_BEER_CHOICE_PROMPT.format(
                image="Есть" if image_file_id else "Нет"
            ),
            reply_markup=get_beer_choice_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_beer_choice)
    except Exception as e:
        logger.error(f"Error processing event image: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.callback_query(lambda c: c.data in ["choice_yes", "choice_no"])
@private_chat_only(response_probability=0.5)
async def process_beer_choice(
    callback_query: types.CallbackQuery, bot: Bot, state: FSMContext
):
    try:
        await callback_query.answer()
        has_beer_choice = callback_query.data == "choice_yes"
        await state.update_data(has_beer_choice=has_beer_choice)
        if has_beer_choice:
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=EVENT_BEER_OPTIONS_PROMPT,
                reply_markup=get_cancel_keyboard(),
            )
            await state.set_state(EventCreationStates.waiting_for_beer_options)
        else:
            await state.update_data(beer_option_1="Лагер", beer_option_2=None)
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=EVENT_NOTIFICATION_CHOICE_PROMPT,
                reply_markup=get_notification_choice_keyboard(),
            )
            await state.set_state(EventCreationStates.waiting_for_notification_choice)
    except Exception as e:
        logger.error(f"Error processing beer choice: {e}", exc_info=True)
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_beer_options)
@private_chat_only(response_probability=0.5)
async def process_beer_options(message: types.Message, bot: Bot, state: FSMContext):
    try:
        input_str = message.text.strip()
        if not re.match(r"[^,]+,[^,]+", input_str):
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_BEER_OPTIONS_INVALID,
                reply_markup=get_cancel_keyboard(),
            )
            return
        beer_options = [option.strip() for option in input_str.split(",")]
        if len(beer_options) != 2 or not all(
            1 <= len(option) <= 100 and option for option in beer_options
        ):
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_BEER_OPTIONS_INVALID,
                reply_markup=get_cancel_keyboard(),
            )
            return
        await state.update_data(
            beer_option_1=beer_options[0], beer_option_2=beer_options[1]
        )
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_NOTIFICATION_CHOICE_PROMPT,
            reply_markup=get_notification_choice_keyboard(),
        )
        await state.set_state(EventCreationStates.waiting_for_notification_choice)
    except Exception as e:
        logger.error(f"Error processing beer options: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.callback_query(lambda c: c.data in ["notify_now", "notify_later"])
@private_chat_only(response_probability=0.5)
async def process_notification_choice(
    callback_query: types.CallbackQuery, bot: Bot, state: FSMContext
):
    try:
        await callback_query.answer()
        notify_now = callback_query.data == "notify_now"
        await state.update_data(notify_now=notify_now)
        if notify_now:
            await finalize_event_creation(
                callback_query.message, bot, state, notify_now=True
            )
        else:
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=EVENT_NOTIFICATION_TIME_PROMPT_SCHEDULED,
                reply_markup=get_cancel_keyboard(),
            )
            await state.set_state(EventCreationStates.waiting_for_notification_time)
    except Exception as e:
        logger.error(f"Error processing notification choice: {e}", exc_info=True)
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.message(EventCreationStates.waiting_for_notification_time)
@private_chat_only(response_probability=0.5)
async def process_notification_time(
    message: types.Message, bot: Bot, state: FSMContext
):
    try:
        time_str = message.text.strip()
        if not re.match(r"^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$", time_str):
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_NOTIFICATION_TIME_INVALID_SCHEDULED,
                reply_markup=get_cancel_keyboard(),
            )
            return
        notification_time = pendulum.from_format(
            time_str, "DD.MM.YYYY HH:mm", tz="Europe/Moscow"
        )
        now = pendulum.now("Europe/Moscow")
        if notification_time <= now:
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_NOTIFICATION_TIME_PAST_SCHEDULED,
                reply_markup=get_cancel_keyboard(),
            )
            return
        # await state.update_data(notification_time=notification_time)
        # Сохраняем notification_time как строку ISO 8601
        await state.update_data(notification_time=notification_time.isoformat())
        await finalize_event_creation(message, bot, state, notify_now=False)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_NOTIFICATION_SCHEDULED.format(
                datetime=notification_time.format("DD.MM.YYYY HH:mm")
            ),
        )
    except pendulum.exceptions.ParserError:
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_NOTIFICATION_TIME_INVALID_SCHEDULED,
            reply_markup=get_cancel_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error processing notification time: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
        await state.clear()


@router.callback_query(lambda c: c.data == "cancel_event_creation")
@private_chat_only(response_probability=0.5)
async def cancel_event_creation(
    callback_query: types.CallbackQuery, bot: Bot, state: FSMContext
):
    try:
        await callback_query.answer()
        await state.clear()
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=EVENT_CANCEL_SUCCESS,
        )
    except Exception as e:
        logger.error(f"Error cancelling event creation: {e}", exc_info=True)
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )


async def finalize_event_creation(
    message: types.Message, bot: Bot, state: FSMContext, notify_now: bool
):
    try:
        data = await state.get_data()
        has_beer_choice = data.get("has_beer_choice", False)
        beer_option_1 = data.get("beer_option_1")
        beer_option_2 = data.get("beer_option_2")
        if has_beer_choice and (not beer_option_1 or not beer_option_2):
            await bot.send_message(
                chat_id=message.chat.id,
                text=EVENT_BEER_OPTIONS_INVALID,
                reply_markup=get_cancel_keyboard(),
            )
            return
        event_date = pendulum.parse(data["event_date"]).date()
        event_time = datetime.strptime(data["event_time"], "%H:%M").time()
        chat_id = int(data["admin_chat_id"])
        user_id = int(data["user_id"])
        notification_time_str = data.get("notification_time")
        notification_time = (
            pendulum.parse(notification_time_str, tz="Europe/Moscow")
            if notification_time_str
            else None
        )
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
            created_by=user_id,
            chat_id=chat_id,
            celery_task_id=None,
            notification_time=notification_time,
        )
        async with get_async_session_context() as session:
            try:
                event = await EventRepository.create_event(session, event_data)
                event_start = pendulum.datetime(
                    year=event.event_date.year,
                    month=event.event_date.month,
                    day=event.event_date.day,
                    hour=event.event_time.hour,
                    minute=event.event_time.minute,
                    tz="Europe/Moscow",
                )
                user_task_id = None
                bartender_task_id = None
                # Планируем задачу для уведомления бармена в event_start
                try:
                    bartender_task = celery_app.send_task(
                        "bot.tasks.bartender_notification.process_bartender_notification",
                        args=(event.id,),
                        eta=event_start,
                    )
                    bartender_task_id = bartender_task.id
                    logger.info(
                        f"Scheduled Celery bartender task {bartender_task_id} for event {event.id} at {event_start}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to schedule bartender task for event {event.id}: {e}",
                        exc_info=True,
                    )
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text="⚠️ Событие создано, но уведомление бармену не запланировано.",
                    )
                    await state.clear()
                    return
                # Планируем задачу для уведомления пользователей
                if notify_now:
                    await send_event_notifications(bot, event)
                else:
                    try:
                        user_task = celery_app.send_task(
                            "bot.tasks.bartender_notification.process_user_notification",
                            args=(event.id,),
                            eta=notification_time,
                        )
                        user_task_id = user_task.id
                        logger.info(
                            f"Scheduled Celery user notification task {user_task_id} for event {event.id} at {notification_time}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to schedule user notification task for event {event.id}: {e}",
                            exc_info=True,
                        )
                        await bot.send_message(
                            chat_id=message.chat.id,
                            text="⚠️ Событие создано, но уведомление пользователям не запланировано.",
                        )
                        await state.clear()
                        return
                # Сохраняем ID задач в базе данных
                if user_task_id or bartender_task_id:
                    stmt = (
                        update(Event)
                        .where(Event.id == event.id)
                        .values(
                            celery_task_id=user_task_id,
                            bartender_task_id=bartender_task_id,
                        )
                    )
                    await session.execute(stmt)
                    await session.commit()
                    logger.info(
                        f"Saved Celery tasks: user_task_id={user_task_id}, bartender_task_id={bartender_task_id} for event {event.id}"
                    )
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
                await bot.send_message(chat_id=message.chat.id, text=summary)
                await bot.send_message(chat_id=message.chat.id, text=EVENT_CREATED)
                logger.info(f"Event created: {event.id} by {message.from_user.id}")
            except IntegrityError as e:
                logger.error(
                    f"Database integrity error creating event: {e}", exc_info=True
                )
                await bot.send_message(
                    chat_id=message.chat.id,
                    text="❌ Ошибка: событие с такими параметрами уже существует.",
                    reply_markup=get_cancel_keyboard(),
                )
                return
            except Exception as e:
                logger.error(f"Unexpected error creating event: {e}", exc_info=True)
                raise
        await state.clear()
    except ProgrammingError as e:
        logger.error(f"Database schema error: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text="❌ Ошибка базы данных. Свяжитесь с администратором.",
            reply_markup=get_cancel_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error finalizing event creation: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=EVENT_ERROR,
            reply_markup=get_cancel_keyboard(),
        )
    finally:
        if await state.get_state():
            await state.clear()


async def send_event_notifications(bot: Bot, event):
    try:
        async with get_async_session_context() as session:
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
    except Exception as e:
        logger.error(f"Error sending event notifications: {e}", exc_info=True)
