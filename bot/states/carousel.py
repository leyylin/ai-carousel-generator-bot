from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    instagram_handle = State()


class CarouselFlow(StatesGroup):
    waiting_topic = State()
    preview = State()
    editing_field = State()
    building = State()
    result = State()
