import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from app.core.config import DEFAULT_PROMPT_TEMPLATE
from app.providers.image_editor.base import (
    ImageEditOptions,
    ImageEditorProvider,
    ImageEditResult,
    ImageOutput,
)

logger = logging.getLogger(__name__)

SIZE_MULTIPLE = 16
OUTPUT_FORMATS = {
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".png": ("PNG", "image/png"),
    ".webp": ("WEBP", "image/webp"),
}


def fit_size(width: int, height: int, max_side: int) -> tuple[int, int]:
    """Scale so the long side equals max_side, keep aspect ratio, snap to SIZE_MULTIPLE."""
    scale = max_side / max(width, height)

    def snap(value: int) -> int:
        return max(SIZE_MULTIPLE, round(value * scale / SIZE_MULTIPLE) * SIZE_MULTIPLE)

    return snap(width), snap(height)


def _is_cuda_oom(exc: Exception) -> bool:
    torch = sys.modules.get("torch")
    return torch is not None and isinstance(exc, torch.cuda.OutOfMemoryError)


def _empty_cuda_cache() -> None:
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


class Flux2KleinImageEditorProvider(ImageEditorProvider):
    name = "flux2_klein"

    def __init__(
        self,
        model_id: str,
        hf_token: str = "",
        device: str = "cuda",
        cpu_offload: bool = False,
        quantization: str = "none",
        num_inference_steps: int = 4,
        guidance_scale: float = 1.0,
        max_image_side: int = 1024,
        seed: int | None = None,
        prompt_template: str = DEFAULT_PROMPT_TEMPLATE,
        pipeline: Any | None = None,
    ) -> None:
        self.model_id = model_id
        self.hf_token = hf_token
        self.device = device
        self.cpu_offload = cpu_offload
        self.quantization = quantization
        self.num_inference_steps = num_inference_steps
        self.guidance_scale = guidance_scale
        self.max_image_side = max_image_side
        self.seed = seed
        self.prompt_template = prompt_template
        self._pipeline = pipeline
        # One GPU, one pipeline: jobs from all worker loops run strictly one at a time.
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        async with self._lock:
            if self._pipeline is None:
                self._pipeline = await asyncio.to_thread(self._load_pipeline)

    async def edit(
        self,
        input_path: Path,
        prompt: str,
        output_path: Path,
        options: ImageEditOptions | None = None,
    ) -> ImageEditResult:
        await self.startup()
        async with self._lock:
            return await asyncio.to_thread(self._edit_sync, input_path, prompt, output_path)

    def build_prompt(self, request: str) -> str:
        return self.prompt_template.format(request=request.strip())

    def _quantization_config(self) -> Any | None:
        if self.quantization == "none":
            return None
        import torch
        from diffusers.quantizers import PipelineQuantizationConfig

        if self.quantization == "4bit":
            backend = "bitsandbytes_4bit"
            quant_kwargs = {
                "load_in_4bit": True,
                "bnb_4bit_quant_type": "nf4",
                "bnb_4bit_compute_dtype": torch.bfloat16,
            }
        else:
            backend = "bitsandbytes_8bit"
            quant_kwargs = {"load_in_8bit": True}
        # Both large components are quantized on load; the small VAE stays in bf16.
        return PipelineQuantizationConfig(
            quant_backend=backend,
            quant_kwargs=quant_kwargs,
            components_to_quantize=["transformer", "text_encoder"],
        )

    def _load_pipeline(self) -> Any:
        import torch
        from diffusers import Flux2KleinPipeline

        started = time.monotonic()
        logger.info(
            "provider=%s model=%s quantization=%s status=loading",
            self.name,
            self.model_id,
            self.quantization,
        )
        pipeline = Flux2KleinPipeline.from_pretrained(
            self.model_id,
            dtype=torch.bfloat16,
            quantization_config=self._quantization_config(),
            token=self.hf_token or None,
        )
        if self.cpu_offload:
            pipeline.enable_model_cpu_offload()
        else:
            pipeline.to(self.device)
        pipeline.set_progress_bar_config(disable=True)
        logger.info(
            "provider=%s model=%s status=loaded quantization=%s cpu_offload=%s seconds=%.1f",
            self.name,
            self.model_id,
            self.quantization,
            self.cpu_offload,
            time.monotonic() - started,
        )
        return pipeline

    def _generator(self) -> Any | None:
        if self.seed is None:
            return None
        import torch

        return torch.Generator(device="cpu").manual_seed(self.seed)

    def _edit_sync(self, input_path: Path, prompt: str, output_path: Path) -> ImageEditResult:
        with Image.open(input_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        source_size = image.size
        width, height = fit_size(*source_size, self.max_image_side)
        full_prompt = self.build_prompt(prompt)

        started = time.monotonic()
        try:
            result = self._pipeline(
                image=image,
                prompt=full_prompt,
                width=width,
                height=height,
                num_inference_steps=self.num_inference_steps,
                guidance_scale=self.guidance_scale,
                generator=self._generator(),
            )
        except Exception as exc:
            if not _is_cuda_oom(exc):
                raise
            _empty_cuda_cache()
            logger.warning("provider=%s status=cuda_oom size=%sx%s", self.name, width, height)
            return ImageEditResult(success=False, provider=self.name, error="GPU out of memory")
        elapsed = time.monotonic() - started

        output = result.images[0].convert("RGB")
        image_format, mime_type = OUTPUT_FORMATS.get(
            output_path.suffix.lower(), OUTPUT_FORMATS[".jpg"]
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_options = {"quality": 95} if image_format in {"JPEG", "WEBP"} else {}
        output.save(output_path, format=image_format, **save_options)

        return ImageEditResult(
            success=True,
            provider=self.name,
            outputs=[ImageOutput(path=output_path, mime_type=mime_type)],
            metadata={
                "model": self.model_id,
                "quantization": self.quantization,
                "source_size": list(source_size),
                "size": [width, height],
                "steps": self.num_inference_steps,
                "guidance_scale": self.guidance_scale,
                "seed": self.seed,
                "seconds": round(elapsed, 2),
            },
        )
