from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

Image = pytest.importorskip("PIL.Image")

from app.providers.image_editor.flux2_klein import (  # noqa: E402
    Flux2KleinImageEditorProvider,
    fit_size,
)


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            images=[Image.new("RGB", (kwargs["width"], kwargs["height"]), "red")]
        )


def make_provider(pipeline: FakePipeline, **kwargs: Any) -> Flux2KleinImageEditorProvider:
    return Flux2KleinImageEditorProvider(model_id="test/model", pipeline=pipeline, **kwargs)


@pytest.mark.parametrize(
    ("size", "max_side", "expected"),
    [
        ((3000, 4000), 1024, (768, 1024)),
        ((4000, 3000), 1024, (1024, 768)),
        ((500, 500), 1024, (1024, 1024)),
        ((1080, 1920), 1024, (576, 1024)),
    ],
)
def test_fit_size_keeps_aspect_ratio_and_multiple_of_16(
    size: tuple[int, int], max_side: int, expected: tuple[int, int]
) -> None:
    width, height = fit_size(*size, max_side)
    assert (width, height) == expected
    assert width % 16 == 0 and height % 16 == 0


def test_build_prompt_wraps_user_request() -> None:
    provider = make_provider(FakePipeline(), prompt_template="Dress in {request}. Keep face.")
    assert provider.build_prompt("  black suit ") == "Dress in black suit. Keep face."


@pytest.mark.asyncio
async def test_edit_calls_pipeline_and_saves_output(tmp_path: Path) -> None:
    source = tmp_path / "person.png"
    Image.new("RGB", (600, 800), "blue").save(source)
    target = tmp_path / "out" / "result.jpg"
    pipeline = FakePipeline()
    provider = make_provider(
        pipeline,
        num_inference_steps=4,
        guidance_scale=1.0,
        prompt_template="Wear {request}",
    )

    result = await provider.edit(source, "red dress", target)

    assert result.success is True
    assert result.provider == "flux2_klein"
    assert result.outputs[0].path == target
    assert result.outputs[0].mime_type == "image/jpeg"
    assert result.metadata["size"] == [768, 1024]
    call = pipeline.calls[0]
    assert call["prompt"] == "Wear red dress"
    assert (call["width"], call["height"]) == (768, 1024)
    assert call["num_inference_steps"] == 4
    assert call["guidance_scale"] == 1.0
    assert call["generator"] is None
    assert call["image"].mode == "RGB"
    with Image.open(target) as saved:
        assert saved.format == "JPEG"
        assert saved.size == (768, 1024)


@pytest.mark.asyncio
async def test_edit_converts_rgba_input(tmp_path: Path) -> None:
    source = tmp_path / "person.png"
    Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(source)
    pipeline = FakePipeline()

    result = await make_provider(pipeline).edit(source, "coat", tmp_path / "result.png")

    assert result.success is True
    assert pipeline.calls[0]["image"].mode == "RGB"
    assert result.outputs[0].mime_type == "image/png"


@pytest.mark.asyncio
async def test_edit_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await make_provider(FakePipeline()).edit(
            tmp_path / "missing.jpg", "coat", tmp_path / "out.jpg"
        )


@pytest.mark.asyncio
async def test_startup_keeps_injected_pipeline() -> None:
    pipeline = FakePipeline()
    provider = make_provider(pipeline)
    await provider.startup()
    assert provider._pipeline is pipeline
