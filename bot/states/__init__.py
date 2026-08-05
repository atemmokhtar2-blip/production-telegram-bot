from aiogram.fsm.state import State, StatesGroup


class CreateBotStates(StatesGroup):
    waiting_description = State()
    trial = State()  # live trial / feedback loop
    waiting_refine = State()  # user requested changes
