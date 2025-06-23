from aiogram import Router, Bot
from aiogram.types import ChatMemberUpdated
from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram.exceptions import TelegramForbiddenError

from db.services import save_group_admin
from db.database import async_session_maker
from bot.logger import setup_logger

router = Router()
logger = setup_logger("group_join")


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, bot: Bot):
    logger.info("Получено обновление my_chat_member")

    try:
        bot_user = await bot.me()

        # Проверка, что обновление касается самого бота
        if event.new_chat_member.user.id != bot_user.id:
            logger.info(
                f"Обновление касается другого пользователя: {event.new_chat_member.user.id}"
            )
            return

        # Проверка, что бот не был исключен или не покинул чат
        if event.new_chat_member.status in [
            ChatMemberStatus.KICKED,
            ChatMemberStatus.LEFT,
        ]:
            logger.warning(
                f"Бот исключен или покинул чат {event.chat.id}, пропускаем обработку"
            )
            return

        admin_id = event.from_user.id
        chat_id = event.chat.id

        # Проверяем, является ли пользователь администратором
        try:
            member = await bot.get_chat_member(chat_id, admin_id)
            if member.status not in [
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            ]:
                logger.warning(f"User {admin_id} is not an admin in chat {chat_id}")
                return
        except TelegramForbiddenError as e:
            logger.warning(
                f"Не удалось проверить статус админа {admin_id} в чате {chat_id}: {e}"
            )
            return

        # Проверка, что бот стал админом
        if (
            event.old_chat_member.status
            in [ChatMemberStatus.LEFT, ChatMemberStatus.MEMBER, ChatMemberStatus.KICKED]
            and event.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR
        ):
            logger.info(f"Бот стал админом в чате {chat_id}, добавил {admin_id}")
            # Создаем сессию и передаем в сервис
            async with async_session_maker() as session:
                try:
                    await save_group_admin(
                        session=session, chat_id=chat_id, user_id=admin_id
                    )
                    logger.info(f"Saved admin {admin_id} for chat {chat_id}")
                except Exception as e:
                    logger.error(f"Error saving group admin: {e}")
        else:
            logger.info(
                f"Изменение прав бота не подходит под нужный критерий. "
                f"Статусы: {event.old_chat_member.status} -> {event.new_chat_member.status}"
            )

    except Exception as e:
        logger.error(f"Ошибка при обработке события my_chat_member: {e}", exc_info=True)
