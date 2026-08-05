from aiogram.fsm.state import State, StatesGroup


class CreateBotStates(StatesGroup):
    waiting_description = State()
