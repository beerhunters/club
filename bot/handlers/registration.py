from aiogram import Router, Bot
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from bot.fsm.registration import Registration
from db.schemas import UserCreate
from bot.core.repositories.user_repository import UserRepository
from bot.core.repositories.group_admin_repository import GroupAdminRepository
from bot.core.repositories.beer_repository import BeerRepository
from bot.texts import (
    NAME_TOO_SHORT,
    ASK_BIRTH_DATE,
    INVALID_DATE_FORMAT,
    REGISTRATION_SUCCESS,
    EVENT_ERROR,
    AGE_RESTRICTION,
    PROFILE_NOT_REGISTERED,
    PROFILE_MESSAGE,
)
from shared.decorators import private_chat_only
from bot.logger import setup_logger
from datetime import datetime
import pendulum

router = Router()
logger = setup_logger("registration")


def get_command_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🍺 Выбрать пиво", callback_data="cmd_beer"))
    builder.add(InlineKeyboardButton(text="👤 Профиль", callback_data="cmd_profile"))
    builder.adjust(2)
    return builder.as_markup()


def get_profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🍺 Выбрать пиво", callback_data="cmd_beer"))
    builder.add(InlineKeyboardButton(text="🏠 В начало", callback_data="cmd_start"))
    builder.adjust(2)
    return builder.as_markup()


@router.message(Registration.name)
@private_chat_only(response_probability=0.5)
async def get_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer(NAME_TOO_SHORT)
        return
    await state.update_data(name=name)
    await state.set_state(Registration.birth_date)
    await message.answer(ASK_BIRTH_DATE)


@router.message(Registration.birth_date)
@private_chat_only(response_probability=0.5)
async def get_birth_date(message: Message, state: FSMContext, session: AsyncSession):
    raw = message.text.strip()
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username
    birth_date = None

    if raw.lower() not in ["-", "нет", "пропустить"]:
        try:
            if raw.count(".") == 1:
                birth_date = datetime.strptime(raw, "%d.%m").replace(year=1900).date()
            elif raw.count(".") == 2:
                birth_date = datetime.strptime(raw, "%d.%m.%Y").date()
                today = pendulum.now("Europe/Moscow")
                age = (
                    today.year
                    - birth_date.year
                    - ((today.month, today.day) < (birth_date.month, birth_date.day))
                )
                if age < 18:
                    await message.answer(AGE_RESTRICTION)
                    return
            else:
                raise ValueError
        except ValueError:
            await message.answer(INVALID_DATE_FORMAT)
            return

    group_id = data["group_id"]
    if not await GroupAdminRepository.group_admin_exists(session, group_id):
        logger.warning(f"Группа {group_id} не зарегистрирована как GroupAdmin")
        await message.answer(EVENT_ERROR)
        await state.clear()
        return

    user_data = UserCreate(
        telegram_id=user_id,
        username=username,
        name=data["name"],
        birth_date=birth_date,
        registered_from_group_id=group_id,
    )

    try:
        user = await UserRepository.create_user(session, user_data)
        await message.answer(REGISTRATION_SUCCESS, reply_markup=get_command_keyboard())
        await state.clear()
        logger.info(f"Зарегистрирован пользователь {user_id}: {user_data}")
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя {user_id}: {e}", exc_info=True)
        await message.answer(EVENT_ERROR)
        await state.clear()


async def show_profile(
    chat_id: int, user_id: int, bot: Bot, state: FSMContext, session: AsyncSession
):
    try:
        user = await UserRepository.get_user_by_id(session, user_id)
        if not user:
            await bot.send_message(chat_id=chat_id, text=PROFILE_NOT_REGISTERED)
            await state.clear()
            return

        birth_date_str = "Не указана"
        age_str = ""
        if user.birth_date and user.birth_date.year != 1900:
            birth_date_str = user.birth_date.strftime("%d.%m.%Y")
            today = pendulum.now("Europe/Moscow")
            age = (
                today.year
                - user.birth_date.year
                - (
                    (today.month, today.day)
                    < (user.birth_date.month, user.birth_date.day)
                )
            )
            age_str = f"{age} лет\n"

        beer_stats = await BeerRepository.get_beer_stats(session, user_id)
        beer_stats_str = "Нет выборов\n"
        if beer_stats:
            beer_stats_str = (
                "\n".join(
                    [f"🍺 {beer}: {count} раз(а)" for beer, count in beer_stats.items()]
                )
                + "\n"
            )

        last_choice = await BeerRepository.get_last_beer_choice(session, user_id)
        last_choice_str = "Нет выборов"
        if last_choice:
            beer_choice, event_name, event_datetime = last_choice
            last_choice_str = f"🍺 {beer_choice} на {event_name} @ {event_datetime}"

        # Преобразование datetime в pendulum.DateTime
        registered_at = (
            pendulum.instance(user.registered_at)
            .in_timezone("Europe/Moscow")
            .format("DD.MM.YYYY HH:mm")
        )

        profile_text = PROFILE_MESSAGE.format(
            name=user.name,
            birth_date=birth_date_str,
            age=age_str,
            telegram_id=user.telegram_id,
            username=user.username or "Не указан",
            registered_at=registered_at,
            beer_stats=beer_stats_str,
            last_choice=last_choice_str,
        )

        await bot.send_message(
            chat_id=chat_id,
            text=profile_text,
            reply_markup=get_profile_keyboard(),
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error in show_profile for user_id={user_id}: {e}", exc_info=True)
        await bot.send_message(
            chat_id=chat_id,
            text=EVENT_ERROR,
        )
        await state.clear()


@router.message(Command("profile"))
@private_chat_only(response_probability=0.5)
async def profile_command_handler(
    message: Message, bot: Bot, state: FSMContext, session: AsyncSession
):
    await show_profile(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        bot=bot,
        state=state,
        session=session,
    )


@router.callback_query(lambda c: c.data == "cmd_profile")
@private_chat_only(response_probability=0.5)
async def profile_callback_handler(
    callback_query: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
):
    try:
        await callback_query.answer()
        await show_profile(
            chat_id=callback_query.message.chat.id,
            user_id=callback_query.from_user.id,
            bot=bot,
            state=state,
            session=session,
        )
    except Exception as e:
        logger.error(f"Error in profile_callback_handler: {e}", exc_info=True)
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=EVENT_ERROR,
        )
        await state.clear()
