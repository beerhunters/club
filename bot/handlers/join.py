from aiogram import Router, Bot
from aiogram.types import ChatMemberUpdated
from aiogram.enums.chat_member_status import ChatMemberStatus

from db.services.group_admin import save_group_admin
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

        # Проверка, что бот стал админом
        if (
            event.old_chat_member.status
            in [ChatMemberStatus.LEFT, ChatMemberStatus.MEMBER, ChatMemberStatus.KICKED]
            and event.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR
        ):

            admin_id = event.from_user.id
            chat_id = event.chat.id

            logger.info(f"Бот стал админом в чате {chat_id}, добавил {admin_id}")
            # Создаем сессию и передаем в сервис
            async with AsyncSessionLocal() as session:
                await save_group_admin(
                    chat_id=chat_id, user_id=admin_id, session=session
                )

        else:
            logger.info(
                f"Изменение прав бота не подходит под нужный критерий. "
                f"Статусы: {event.old_chat_member.status} -> {event.new_chat_member.status}"
            )

    except Exception as e:
        logger.error(f"Ошибка при обработке события my_chat_member: {e}", exc_info=True)
