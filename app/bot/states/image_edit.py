from aiogram.fsm.state import State, StatesGroup


class ImageEditStates(StatesGroup):
    waiting_image = State()
    waiting_prompt = State()
    processing = State()
