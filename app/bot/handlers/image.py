from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.states.image_edit import ImageEditStates
from app.core.config import Settings
from app.services.storage_service import InvalidImageError, StorageService

router = Router(name="image")


async def _receive_image(
    message: Message,
    state: FSMContext,
    bot: Bot,
    storage_service: StorageService,
    settings: Settings,
) -> None:
    if message.photo:
        telegram_file = message.photo[-1]
        mime_type = "image/jpeg"
    elif message.document:
        telegram_file = message.document
        mime_type = message.document.mime_type
    else:
        await message.answer("Отправьте изображение как фото или файл.")
        return
    if telegram_file.file_size and telegram_file.file_size > settings.max_image_size_bytes:
        await message.answer(f"Файл больше допустимых {settings.max_image_size_mb} МБ.")
        return
    buffer = BytesIO()
    try:
        await bot.download(telegram_file.file_id, destination=buffer)
        path = await storage_service.save_input(buffer.getvalue(), mime_type)
    except InvalidImageError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer("Не удалось скачать или сохранить изображение. Попробуйте ещё раз.")
        return
    await state.update_data(input_path=str(path), telegram_file_id=telegram_file.file_id)
    await state.set_state(ImageEditStates.waiting_prompt)
    await message.answer("Изображение получено. Теперь напишите, что нужно изменить.")


@router.message(ImageEditStates.waiting_image, F.photo)
async def receive_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    storage_service: StorageService,
    settings: Settings,
) -> None:
    await _receive_image(message, state, bot, storage_service, settings)


@router.message(ImageEditStates.waiting_image, F.document)
async def receive_document(
    message: Message,
    state: FSMContext,
    bot: Bot,
    storage_service: StorageService,
    settings: Settings,
) -> None:
    await _receive_image(message, state, bot, storage_service, settings)


@router.message(ImageEditStates.waiting_image)
async def require_image(message: Message) -> None:
    await message.answer("Сначала отправьте изображение (JPEG, PNG или WEBP).")
