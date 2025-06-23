from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from bot.fsm.registration import Registration
from db.services.user import save_user


router = Router()


@router.message(F.text.startswith("/registration registration_"))
async def registration_entry(
    message: Message, state: FSMContext, command: CommandObject
):
    group_id = int(command.args.split("_")[1])
    await state.update_data(group_id=group_id)
    await state.set_state(Registration.name)
    await message.answer("Введите ваше имя:")


@router.message(Registration.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Registration.birth_date)
    await message.answer(
        "Введите дату рождения (ДД.ММ.ГГГГ или ДД.ММ) или отправьте '-' для пропуска:"
    )


@router.message(Registration.birth_date)
async def get_birth_date(message: Message, state: FSMContext, session: AsyncSession):
    raw = message.text.strip()
    data = await state.get_data()
    birth_date = None

    if raw != "-":
        try:
            if len(raw.split(".")) == 2:
                birth_date = datetime.strptime(raw, "%d.%m").replace(
                    year=1900
                )  # условный год
            elif len(raw.split(".")) == 3:
                birth_date = datetime.strptime(raw, "%d.%m.%Y")
        except ValueError:
            await message.answer("Неверный формат. Повторите ввод:")
            return

    await save_user(
        session=session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        name=data["name"],
        birth_date=birth_date,
        group_id=data["group_id"],
    )
    await message.answer("Регистрация завершена ✅")
    await state.clear()
