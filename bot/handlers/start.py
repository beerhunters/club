from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.user_repository import UserRepository
from bot.texts import (
    START_SIMPLE_TEXT,
    START_ALREADY_REGISTERED,
    START_REGISTER_BUTTON,
    INVALID_LINK_FORMAT,
    GREET_NAME,
    ALREADY_REGISTERED_IN_GROUP,
    REGISTER_IN_PRIVATE,
)
from bot.fsm.registration import Registration
from bot.logger import setup_logger

router = Router()
logger = setup_logger("start")


def get_command_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🍺 Выбрать пиво", callback_data="select_beer")
    )
    builder.add(InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    builder.adjust(2)
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    user_id = message.from_user.id
    text_parts = message.text.split(maxsplit=1)
    logger.info(f"/start от {user_id}, текст: {message.text}")

    # Пользователь пришел по диплинку в ЛС
    if (
        message.chat.type == "private"
        and len(text_parts) == 2
        and text_parts[1].startswith("registration_")
    ):
        try:
            group_id = int(text_parts[1].split("_")[1])
        except (IndexError, ValueError):
            logger.warning("Неверный формат ссылки регистрации")
            await message.answer(INVALID_LINK_FORMAT)
            return

        user = await UserRepository.get_user_by_id(session, user_id)
        if user:
            await message.answer(
                START_ALREADY_REGISTERED, reply_markup=get_command_keyboard()
            )
        else:
            await state.set_state(Registration.name)
            await state.update_data(group_id=group_id)
            logger.info(
                f"Пользователь {user_id} начал регистрацию из группы {group_id}"
            )
            await message.answer(GREET_NAME)
        return

    # Команда /start в группе
    if message.chat.type in ("group", "supergroup"):
        user = await UserRepository.get_user_by_id(session, user_id)
        if user:
            await message.reply(ALREADY_REGISTERED_IN_GROUP)
        else:
            group_id = message.chat.id
            bot_user = await message.bot.get_me()
            deeplink = f"https://t.me/{bot_user.username}?start=registration_{group_id}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=START_REGISTER_BUTTON, url=deeplink)]
                ]
            )
            await message.reply(
                REGISTER_IN_PRIVATE,
                reply_markup=keyboard,
            )
        return

    # Просто /start в личке без аргументов
    await message.answer(START_SIMPLE_TEXT, reply_markup=get_command_keyboard())
