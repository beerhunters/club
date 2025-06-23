# from aiogram import Router
# from aiogram.types import Message
# from bot.texts import START_TEXT
# from aiogram.filters import CommandStart
#
# router = Router()
#
#
# @router.message(CommandStart())
# async def cmd_start(message: Message):
#     await message.answer(START_TEXT)
#
#
# def register_start(dp):
#     dp.include_router(router)
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from db.services.user import get_user_by_id
from bot.texts import START_TEXT, START_ALREADY_REGISTERED, START_REGISTER_BUTTON

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    if message.chat.type in ("group", "supergroup"):
        user = await get_user_by_id(session, message.from_user.id)
        if user:
            await message.reply("Вы уже зарегистрированы.")
        else:
            group_id = message.chat.id
            bot_user = await message.bot.get_me()
            deeplink = (
                f"https://t.me/{bot_user.username}?registration=registration_{group_id}"
            )
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Зарегистрироваться", url=deeplink)]
                ]
            )
            await message.reply(
                "Пройдите регистрацию в личных сообщениях с ботом:",
                reply_markup=keyboard,
            )
    else:
        await message.answer(START_TEXT)


def register_start(dp):
    dp.include_router(router)
