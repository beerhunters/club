from aiogram import Dispatcher, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent
from bot.logger import logger
from shared.config import settings

ERROR_CHAT_ID = settings.ERROR_CHAT_ID


def setup_error_handler(dp: Dispatcher, bot: Bot):
    @dp.errors()
    async def error_handler(event: ErrorEvent):
        logger.error(f"Unhandled error: {event.exception}")
        try:
            await bot.send_message(ERROR_CHAT_ID, f"❗ Ошибка: {event.exception}")
        except TelegramAPIError:
            logger.error("Не удалось отправить сообщение об ошибке")
