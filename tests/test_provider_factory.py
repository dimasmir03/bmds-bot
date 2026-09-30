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


def test_factory_creates_flux2_klein_provider_without_loading_model() -> None:
    pytest.importorskip("PIL")
    from app.providers.image_editor.flux2_klein import Flux2KleinImageEditorProvider

    provider = create_image_editor_provider(
        Settings(
            image_provider="flux2_klein",
            hf_model_id="test/model",
            model_cpu_offload=True,
            model_quantization="4bit",
            model_max_image_side=768,
            model_seed=7,
        )
    )
    assert isinstance(provider, Flux2KleinImageEditorProvider)
    assert provider.model_id == "test/model"
    assert provider.cpu_offload is True
    assert provider.quantization == "4bit"
    assert provider.max_image_side == 768
    assert provider.seed == 7
    assert provider._pipeline is None


def test_settings_reject_prompt_template_without_request() -> None:
    with pytest.raises(ValueError):
        Settings(model_prompt_template="Change clothes")


def test_settings_reject_unknown_quantization() -> None:
    with pytest.raises(ValueError):
        Settings(model_quantization="2bit")


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(UnsupportedProviderError):
        create_image_editor_provider(Settings(image_provider="unknown"))
