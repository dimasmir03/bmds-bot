from pathlib import Path

from app.providers.image_editor.base import ImageEditorProvider, ImageEditResult
from app.services.storage_service import StorageService


class ImageService:
    def __init__(self, storage: StorageService, provider: ImageEditorProvider) -> None:
        self.storage = storage
        self.provider = provider

    async def edit(self, input_path: Path, prompt: str) -> ImageEditResult:
        output_path = self.storage.output_path_for(input_path)
        return await self.provider.edit(input_path, prompt, output_path)
