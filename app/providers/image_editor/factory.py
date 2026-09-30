from app.core.config import Settings
from app.providers.image_editor.base import ImageEditorProvider
from app.providers.image_editor.mock import MockImageEditorProvider


class UnsupportedProviderError(ValueError):
    pass


def create_image_editor_provider(settings: Settings) -> ImageEditorProvider:
    if settings.image_provider == "mock":
        return MockImageEditorProvider(settings.mock_processing_delay_seconds)
    if settings.image_provider == "flux2_klein":
        # Imported lazily: torch/diffusers are installed only in the worker image.
        from app.providers.image_editor.flux2_klein import Flux2KleinImageEditorProvider

        return Flux2KleinImageEditorProvider(
            model_id=settings.hf_model_id,
            hf_token=settings.hf_token,
            device=settings.model_device,
            cpu_offload=settings.model_cpu_offload,
            quantization=settings.model_quantization,
            num_inference_steps=settings.model_num_inference_steps,
            guidance_scale=settings.model_guidance_scale,
            max_image_side=settings.model_max_image_side,
            seed=settings.model_seed,
            prompt_template=settings.model_prompt_template,
        )
    raise UnsupportedProviderError(f"Unsupported image provider: {settings.image_provider}")
