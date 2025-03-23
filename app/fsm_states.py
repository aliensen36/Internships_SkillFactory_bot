from aiogram.fsm.state import State, StatesGroup

class BroadcastState(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()


class SpecializationStates(StatesGroup):
    waiting_for_specialization = State()