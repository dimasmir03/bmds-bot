from pathlib import Path

import pytest

from app.services.storage_service import (
    ImageTooLargeError,
    InvalidImageError,
    StorageService,
)


@pytest.mark.asyncio
async def test_storage_saves_uuid_image_below_root(tmp_path: Path) -> None:
    storage = StorageService(tmp_path, 1024)
    content = b"\x89PNG\r\n\x1a\nrest"

    path = await storage.save_input(content, "image/png")

    assert path.read_bytes() == content
    assert path.suffix == ".png"
    assert storage.root in path.parents
    assert path.name != "photo.png"


@pytest.mark.parametrize(
    ("content", "mime_type"),
    [(b"not a png", "image/png"), (b"GIF89a", "image/gif"), (b"", "image/jpeg")],
)
def test_storage_rejects_invalid_image(tmp_path: Path, content: bytes, mime_type: str) -> None:
    storage = StorageService(tmp_path, 1024)
    with pytest.raises(InvalidImageError):
        storage.validate_image(content, mime_type)


def test_storage_rejects_large_image(tmp_path: Path) -> None:
    storage = StorageService(tmp_path, 8)
    with pytest.raises(ImageTooLargeError):
        storage.validate_image(b"\x89PNG\r\n\x1a\nmore", "image/png")
