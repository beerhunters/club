from aiogram.fsm.state import State, StatesGroup


class EventCreationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_location = State()
    waiting_for_location_name = State()
    waiting_for_description = State()
    waiting_for_image = State()
    waiting_for_beer_choice = State()
    waiting_for_beer_options = State()
    waiting_for_notification_choice = State()
    waiting_for_notification_time = State()