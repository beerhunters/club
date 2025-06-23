from aiogram import Router, Bot
from aiogram.types import ChatMemberUpdated
from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.group_admin_repository import GroupAdminRepository
from db.schemas import GroupAdminCreate
from bot.logger import setup_logger

router = Router()
logger = setup_logger("group_join")


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, bot: Bot, session: AsyncSession):
    logger.info("Получено обновление my_chat_member")
    try:
        bot_user = await bot.me()
        if event.new_chat_member.user.id != bot_user.id:
            logger.info(
                f"Обновление касается другого пользователя: {event.new_chat_member.user.id}"
            )
            return
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
        try:
            member = await bot.get_chat_member(chat_id, admin_id)
            if member.status not in [
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            ]:
                logger.warning(
                    f"Пользователь {admin_id} не является администратором в чате {chat_id}"
                )
                return
        except TelegramForbiddenError as e:
            logger.warning(
                f"Не удалось проверить статус администратора {admin_id} в чате {chat_id}: {e}"
            )
            return
        if (
            event.old_chat_member.status
            in [ChatMemberStatus.LEFT, ChatMemberStatus.MEMBER, ChatMemberStatus.KICKED]
            and event.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR
        ):
            logger.info(
                f"Бот стал администратором в чате {chat_id}, добавил {admin_id}"
            )
            try:
                group_admin_data = GroupAdminCreate(chat_id=chat_id, user_id=admin_id)
                await GroupAdminRepository.create_group_admin(
                    session=session, group_admin_data=group_admin_data
                )
                logger.info(f"Сохранен администратор {admin_id} для чата {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка сохранения администратора группы: {e}")
                raise
        else:
            logger.info(
                f"Изменение прав бота не подходит под критерий. Статусы: {event.old_chat_member.status} -> {event.new_chat_member.status}"
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке события my_chat_member: {e}", exc_info=True)
