from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    name = State()
    birth_date = State()
