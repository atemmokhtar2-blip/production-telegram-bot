from aiogram.fsm.state import State, StatesGroup


class CreateBotStates(StatesGroup):
    waiting_description = State()
    waiting_trial_token = State()
