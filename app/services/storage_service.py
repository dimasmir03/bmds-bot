import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),
}


class InvalidImageError(ValueError):
    pass


class ImageTooLargeError(InvalidImageError):
    pass


class StorageService:
    def __init__(self, root: Path, max_size_bytes: int) -> None:
        self.root = root.resolve()
        self.max_size_bytes = max_size_bytes
        for directory in ("input", "output", "temp"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)

    def validate_image(self, data: bytes, mime_type: str | None) -> str:
        if mime_type not in SUPPORTED_IMAGE_TYPES:
            raise InvalidImageError("Поддерживаются только JPEG, PNG и WEBP.")
        if len(data) > self.max_size_bytes:
            raise ImageTooLargeError("Изображение слишком большое.")
        if not data:
            raise InvalidImageError("Получен пустой файл.")
        extension, signatures = SUPPORTED_IMAGE_TYPES[mime_type]
        if mime_type == "image/webp":
            valid = data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP"
        else:
            valid = any(data.startswith(signature) for signature in signatures)
        if not valid:
            raise InvalidImageError("Содержимое файла не соответствует типу изображения.")
        return extension

    def new_path(self, area: str, extension: str) -> Path:
        if area not in {"input", "output", "temp"}:
            raise ValueError("Unknown storage area")
        now = datetime.now(UTC)
        path = self.root / area / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}"
        path.mkdir(parents=True, exist_ok=True)
        result = (path / f"{uuid.uuid4()}{extension.lower()}").resolve()
        if self.root not in result.parents:
            raise ValueError("Unsafe storage path")
        return result

    async def save_input(self, data: bytes, mime_type: str | None) -> Path:
        extension = self.validate_image(data, mime_type)
        path = self.new_path("input", extension)
        await asyncio.to_thread(path.write_bytes, data)
        return path

    def output_path_for(self, input_path: Path) -> Path:
        suffix = input_path.suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".jpg"
        return self.new_path("output", suffix)

    async def remove(self, path: Path) -> None:
        resolved = await asyncio.to_thread(path.resolve)
        if self.root not in resolved.parents:
            raise ValueError("Refusing to remove a path outside storage")

        def unlink_if_present() -> None:
            if resolved.exists():
                resolved.unlink()

        await asyncio.to_thread(unlink_if_present)
