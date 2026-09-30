from app.core.config import Settings
from app.providers.image_editor.base import ImageEditorProvider
from app.providers.image_editor.mock import MockImageEditorProvider


class UnsupportedProviderError(ValueError):
    pass


def create_image_editor_provider(settings: Settings) -> ImageEditorProvider:
    if settings.image_provider == "mock":
        return MockImageEditorProvider(settings.mock_processing_delay_seconds)
    raise UnsupportedProviderError(f"Unsupported image provider: {settings.image_provider}")
