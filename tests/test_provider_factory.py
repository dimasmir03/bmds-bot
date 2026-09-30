import pytest

from app.core.config import Settings
from app.providers.image_editor.factory import (
    UnsupportedProviderError,
    create_image_editor_provider,
)
from app.providers.image_editor.mock import MockImageEditorProvider


def test_factory_creates_mock_provider() -> None:
    provider = create_image_editor_provider(
        Settings(image_provider="mock", mock_processing_delay_seconds=0.25)
    )
    assert isinstance(provider, MockImageEditorProvider)
    assert provider.delay_seconds == 0.25


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(UnsupportedProviderError):
        create_image_editor_provider(Settings(image_provider="unknown"))
