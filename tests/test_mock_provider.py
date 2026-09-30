from pathlib import Path

import pytest

from app.providers.image_editor.mock import MockImageEditorProvider


@pytest.mark.asyncio
async def test_mock_provider_copies_input(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "nested" / "result.png"
    source.write_bytes(b"image-content")

    result = await MockImageEditorProvider(delay_seconds=0).edit(source, "change", target)

    assert result.success is True
    assert result.provider == "mock"
    assert result.outputs[0].path == target
    assert result.metadata["mock"] is True
    assert target.read_bytes() == b"image-content"


@pytest.mark.asyncio
async def test_mock_provider_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await MockImageEditorProvider(0).edit(
            tmp_path / "missing.jpg", "change", tmp_path / "out.jpg"
        )
