from aiogram import Dispatcher, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent, Update
import traceback
import pendulum

from bot.logger import setup_logger
from shared.config import settings

ERROR_CHAT_ID = settings.ERROR_CHAT_ID
logger = setup_logger("error")


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def get_user_info(update: Update):
    if not update:
        return None, None, None
    if update.message:
        user = update.message.from_user
        return user.id, user.full_name, update.message.text
    elif update.callback_query:
        user = update.callback_query.from_user
        return user.id, user.full_name, update.callback_query.data
    return None, None, None


def get_traceback(exc: Exception):
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    snippet = "".join(tb[-4:])  # последние 4 строки
    return escape_html(snippet[:2000])  # ограничение Telegram


def get_location(exc: Exception):
    tb = traceback.extract_tb(exc.__traceback__)
    if not tb:
        return "❓ Неизвестное местоположение"
    last = tb[-1]
    filename = escape_html(last.filename)
    line = last.lineno
    func = escape_html(last.name)
    code_line = escape_html(last.line.strip()) if last.line else "???"
    return (
        f"📂 <b>Файл:</b> {filename}\n"
        f"📌 <b>Строка:</b> {line}\n"
        f"🔹 <b>Функция:</b> {func}\n"
        f"🖥 <b>Код:</b> <pre>{code_line}</pre>"
    )


def setup_error_handler(dp: Dispatcher, bot: Bot):
    @dp.errors()
    async def error_handler(event: ErrorEvent):
        exc = event.exception
        update = event.update

        filename = exc.__traceback__.tb_frame.f_code.co_filename
        line = exc.__traceback__.tb_lineno
        logger.error(
            f"Unhandled error: {type(exc).__name__} at {filename}:{line} - {str(exc)}"
        )

        user_id, user_name, user_msg = get_user_info(update)
        location = get_location(exc)
        tb_snippet = get_traceback(exc)

        now = pendulum.now("Europe/Moscow").format("YYYY-MM-DD HH:mm:ss ZZ")

        admin_message = (
            f"⚠️ <b>Ошибка в боте!</b>\n\n"
            f"⏰ <b>Время:</b> {now}\n\n"
            f"👤 <b>Пользователь:</b> {escape_html(user_name or 'Неизвестно')}\n"
            f"🆔 <b>ID:</b> {user_id or 'Неизвестно'}\n"
            f"💬 <b>Сообщение:</b> {escape_html(user_msg or 'Неизвестно')}\n\n"
            f"❌ <b>Тип ошибки:</b> {escape_html(type(exc).__name__)}\n"
            f"📝 <b>Описание:</b> {escape_html(str(exc))}\n\n"
            f"📍 <b>Местоположение:</b>\n{location}\n\n"
            f"📚 <b>Трейсбек:</b>\n<pre>{tb_snippet}</pre>"
        )

        try:
            await bot.send_message(ERROR_CHAT_ID, admin_message, parse_mode="HTML")
        except TelegramAPIError as tg_error:
            logger.error(f"Ошибка отправки уведомления в Telegram: {tg_error}")
