from aiogram.fsm.state import State, StatesGroup


class BeerSelectionStates(StatesGroup):
    selecting_event = State()
    confirming_location = State()
    selecting_beer = State()
