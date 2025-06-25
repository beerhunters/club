from math import radians, sin, cos, sqrt, atan2

from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.event_repository import EventRepository
from bot.core.repositories.beer_repository import BeerRepository
from bot.core.repositories.user_repository import UserRepository
from bot.fsm.beer import BeerSelectionStates
from db.schemas import BeerSelectionCreate
from bot.texts import (
    BEER_NO_EVENTS,
    BEER_EVENT_LIST,
    BEER_EVENT_TOO_LATE,
    BEER_ALREADY_SELECTED,
    BEER_EVENT_FULL_INFO,
    BEER_REQUEST_LOCATION,
    BEER_INVALID_LOCATION,
    BEER_CHOICE_PROMPT,
    BEER_CHOICE_SUCCESS,
    BEER_ERROR,
    BEER_TOO_FAR,
)
from shared.decorators import private_chat_only
from bot.logger import setup_logger
from db.database import get_async_session_context
from datetime import datetime
import pendulum
from typing import Optional

logger = setup_logger(__name__)
router = Router()


def get_event_list_keyboard(events):
    builder = InlineKeyboardBuilder()
    for event in events:
        event_time = event.event_time.strftime("%H:%M")
        button_text = (
            f"{event.name} @ {event.event_date.strftime('%d.%m.%Y')} {event_time}"
        )
        builder.add(
            types.InlineKeyboardButton(
                text=button_text, callback_data=f"select_event_{event.id}"
            )
        )
    builder.adjust(1)
    return builder.as_markup()


def get_beer_choice_keyboard(event):
    builder = InlineKeyboardBuilder()
    if event.has_beer_choice:
        builder.add(
            types.InlineKeyboardButton(
                text=event.beer_option_1, callback_data=f"beer_{event.beer_option_1}"
            )
        )
        builder.add(
            types.InlineKeyboardButton(
                text=event.beer_option_2, callback_data=f"beer_{event.beer_option_2}"
            )
        )
        builder.adjust(2)
    else:
        builder.add(
            types.InlineKeyboardButton(text="Лагер", callback_data="beer_Лагер")
        )
    return builder.as_markup()


EARTH_RADIUS_M = 6371000  # Радиус Земли в метрах


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if not all(isinstance(x, (int, float)) and -90 <= x <= 90 for x in (lat1, lat2)):
        raise ValueError("Latitudes must be between -90 and 90 degrees")
    if not all(isinstance(x, (int, float)) and -180 <= x <= 180 for x in (lon1, lon2)):
        raise ValueError("Longitudes must be between -180 and 180 degrees")
    if not all(
        isinstance(x, (int, float)) and x == x for x in (lat1, lon1, lat2, lon2)
    ):
        raise ValueError("Coordinates must be finite numbers")
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = EARTH_RADIUS_M * c
    return distance


async def start_beer_selection(
    chat_id: int,
    user_id: int,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
):
    """
    Запускает процесс выбора пива: проверяет регистрацию, получает события и отправляет список.
    """
    try:
        # Проверяем, зарегистрирован ли пользователь
        user = await UserRepository.get_user_by_id(session, user_id)
        if not user:
            await bot.send_message(
                chat_id=chat_id,
                text=BEER_ERROR.format(error="Вы не зарегистрированы."),
            )
            return

        # Получаем актуальные события
        # Можно использовать get_upcoming_events_by_date(date=today) для конкретной даты
        events = await EventRepository.get_upcoming_events(session, limit=100)

        # Фильтруем события, которые ещё не начались
        now = pendulum.now("Europe/Moscow")
        upcoming_events = [
            event
            for event in events
            if pendulum.datetime(
                event.event_date.year,
                event.event_date.month,
                event.event_date.day,
                event.event_time.hour,
                event.event_time.minute,
                tz="Europe/Moscow",
            )
            > now
        ]

        if not upcoming_events:
            await bot.send_message(
                chat_id=chat_id,
                text=BEER_NO_EVENTS,
            )
            return

        await bot.send_message(
            chat_id=chat_id,
            text=BEER_EVENT_LIST,
            reply_markup=get_event_list_keyboard(upcoming_events),
        )
        await state.set_state(BeerSelectionStates.selecting_event)
    except Exception as e:
        logger.error(f"Error in start_beer_selection: {e}", exc_info=True)
        await bot.send_message(
            chat_id=chat_id,
            text=BEER_ERROR.format(error="Произошла ошибка."),
        )
        await state.clear()


@router.message(Command("beer"))
@private_chat_only(response_probability=0.5)
async def beer_command_handler(
    message: types.Message, bot: Bot, state: FSMContext, session: AsyncSession
):
    """Обрабатывает команду /beer."""
    await start_beer_selection(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        bot=bot,
        state=state,
        session=session,
    )


@router.callback_query(lambda c: c.data == "cmd_beer")
@private_chat_only(response_probability=0.5)
async def beer_callback_handler(
    callback_query: types.CallbackQuery,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
):
    """Обрабатывает нажатие на кнопку 'Выбрать пиво'."""
    try:
        await callback_query.answer()
        await start_beer_selection(
            chat_id=callback_query.message.chat.id,
            user_id=callback_query.from_user.id,
            bot=bot,
            state=state,
            session=session,
        )
    except Exception as e:
        logger.error(f"Error in beer_callback_handler: {e}", exc_info=True)
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=BEER_ERROR.format(error="Произошла ошибка."),
        )
        await state.clear()


@router.callback_query(lambda c: c.data.startswith("select_event_"))
@private_chat_only(response_probability=0.5)
async def select_event_handler(
    callback_query: types.CallbackQuery,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
):
    try:
        await callback_query.answer()
        event_id = int(callback_query.data.split("_")[-1])
        user_id = callback_query.from_user.id

        # Получаем событие
        event = await EventRepository.get_event_by_id(session, event_id)
        if not event:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text=BEER_ERROR.format(error="Событие не найдено."),
            )
            await state.clear()
            return

        # Проверяем, не сделал ли пользователь выбор
        existing_selection = await BeerRepository.get_user_selection(
            session, user_id, event_id
        )
        if existing_selection:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text=BEER_ALREADY_SELECTED.format(beer=existing_selection.beer_choice),
            )
            await state.clear()
            return

        # Проверяем, что до старта события не более 30 минут
        now = pendulum.now("Europe/Moscow")
        event_start = pendulum.datetime(
            event.event_date.year,
            event.event_date.month,
            event.event_date.day,
            event.event_time.hour,
            event.event_time.minute,
            tz="Europe/Moscow",
        )
        time_diff = event_start - now
        if time_diff.total_minutes() > 30 or event_start <= now:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text=BEER_EVENT_TOO_LATE,
            )
            await state.clear()
            return

        # Сохраняем данные события
        await state.update_data(event_id=event_id, chat_id=event.chat_id)

        # Отправляем полное описание события
        beer_options = (
            f"{event.beer_option_1}, {event.beer_option_2}"
            if event.has_beer_choice
            else "Лагер"
        )
        event_info = BEER_EVENT_FULL_INFO.format(
            name=event.name,
            date=event.event_date.strftime("%d.%m.%Y"),
            time=event.event_time.strftime("%H:%M"),
            location=event.location_name or "Не указано",
            description=event.description or "Не указано",
            beer_options=beer_options,
        )
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=event_info,
        )

        # Проверяем, есть ли геопозиция
        if event.latitude is not None and event.longitude is not None:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text=BEER_REQUEST_LOCATION,
            )
            await state.set_state(BeerSelectionStates.confirming_location)
        else:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text=BEER_CHOICE_PROMPT,
                reply_markup=get_beer_choice_keyboard(event),
            )
            await state.set_state(BeerSelectionStates.selecting_beer)

    except Exception as e:
        logger.error(f"Error in select_event_handler: {e}", exc_info=True)
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=BEER_ERROR.format(error="Произошла ошибка."),
        )
        await state.clear()


@router.message(BeerSelectionStates.confirming_location)
@private_chat_only(response_probability=0.5)
async def confirm_location_handler(
    message: types.Message, bot: Bot, state: FSMContext, session: AsyncSession
):
    try:
        if not message.location:
            await bot.send_message(
                chat_id=message.chat.id,
                text=BEER_INVALID_LOCATION,
            )
            return

        data = await state.get_data()
        event_id = data["event_id"]
        event = await EventRepository.get_event_by_id(session, event_id)
        if not event:
            await bot.send_message(
                chat_id=message.chat.id,
                text=BEER_ERROR.format(error="Событие не найдено."),
            )
            await state.clear()
            return

        # Проверяем расстояние до места события
        distance = haversine_distance(
            message.location.latitude,
            message.location.longitude,
            event.latitude,
            event.longitude,
        )
        logger.debug(f"Distance between user and event: {distance:.2f} meters")
        if distance > 300:
            await bot.send_message(
                chat_id=message.chat.id,
                text=BEER_TOO_FAR,
            )
            return

        await bot.send_message(
            chat_id=message.chat.id,
            text=BEER_CHOICE_PROMPT,
            reply_markup=get_beer_choice_keyboard(event),
        )
        await state.set_state(BeerSelectionStates.selecting_beer)

    except Exception as e:
        logger.error(f"Error in confirm_location_handler: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=BEER_ERROR.format(error="Произошла ошибка."),
        )
        await state.clear()


@router.callback_query(lambda c: c.data.startswith("beer_"))
@private_chat_only(response_probability=0.5)
async def select_beer_handler(
    callback_query: types.CallbackQuery,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
):
    try:
        await callback_query.answer()
        beer_choice = callback_query.data.split("_")[-1]
        user_id = callback_query.from_user.id
        data = await state.get_data()
        event_id = data["event_id"]
        chat_id = data["chat_id"]

        # Создаём запись о выборе
        selection_data = BeerSelectionCreate(
            user_id=user_id,
            event_id=event_id,
            chat_id=chat_id,
            beer_choice=beer_choice,
        )
        async with get_async_session_context() as session:
            selection = await BeerRepository.create_beer_selection(
                session, selection_data
            )

        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=BEER_CHOICE_SUCCESS.format(beer=beer_choice),
        )
        logger.info(
            f"User {user_id} selected beer '{beer_choice}' for event {event_id}"
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Error in select_beer_handler: {e}", exc_info=True)
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=BEER_ERROR.format(error="Произошла ошибка."),
        )
        await state.clear()
