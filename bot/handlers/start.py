from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from db.services import get_user_by_id
from bot.texts import START_TEXT, START_ALREADY_REGISTERED, START_REGISTER_BUTTON
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
            logger.warning("Invalid registration link format.")
            await message.answer("Неверный формат ссылки регистрации.")
            return

        user = await get_user_by_id(session, user_id)
        if user:
            await message.answer(START_ALREADY_REGISTERED)
        else:
            await state.set_state(Registration.name)
            await state.update_data(group_id=group_id)
            logger.info(f"User {user_id} starts registration from group {group_id}")
            await message.answer("Привет! Как тебя зовут?")
        return

    # Команда /start в группе
    if message.chat.type in ("group", "supergroup"):
        user = await get_user_by_id(session, user_id)
        if user:
            await message.reply("Вы уже зарегистрированы.")
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
                "Пройдите регистрацию в личных сообщениях с ботом:",
                reply_markup=keyboard,
            )
        return

    # Просто /start в личке без аргументов
    await message.answer(START_TEXT)
