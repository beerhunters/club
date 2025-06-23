from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from db.services import get_user_by_id
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


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    user_id = message.from_user.id
    text_parts = message.text.split(maxsplit=1)
    logger.info(f"/start from {user_id}, text: {message.text}")

    # Пользователь пришёл по диплинку в ЛС
    if (
        message.chat.type == "private"
        and len(text_parts) == 2
        and text_parts[1].startswith("registration_")
    ):
        try:
            group_id = int(text_parts[1].split("_")[1])
        except (IndexError, ValueError):
            logger.warning("Invalid registration link format")
            await message.answer(INVALID_LINK_FORMAT)
            return

        user = await get_user_by_id(session, user_id)
        if user:
            await message.answer(START_ALREADY_REGISTERED)
        else:
            await state.set_state(Registration.name)
            await state.update_data(group_id=group_id)
            logger.info(f"User {user_id} starts registration from group {group_id}")
            await message.answer(GREET_NAME)
        return

    # Команда /start в группе
    if message.chat.type in ("group", "supergroup"):
        user = await get_user_by_id(session, user_id)
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
    await message.answer(START_SIMPLE_TEXT)
