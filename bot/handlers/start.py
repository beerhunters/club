from aiogram import Router
from aiogram.types import Message
from bot.texts import START_TEXT
from aiogram.filters import CommandStart

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(START_TEXT)
    1 / 0


def register_start(dp):
    dp.include_router(router)
