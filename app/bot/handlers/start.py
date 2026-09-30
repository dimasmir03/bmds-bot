from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.states.image_edit import ImageEditStates

router = Router(name="start")

WELCOME = (
    "Я покажу, как вы будете выглядеть в другой одежде.\n\n"
    "1. Отправьте своё фото (JPEG, PNG, WEBP или HEIC), лучше в полный рост.\n"
    "2. Опишите, во что вас одеть, например: «чёрный классический костюм». "
    "Можно сразу подписью к фото.\n"
    "3. Дождитесь результата."
)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ImageEditStates.waiting_image)
    await message.answer(WELCOME)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        f"{WELCOME}\n\n/status — состояние последней задачи\n/cancel — отменить текущую задачу"
    )
