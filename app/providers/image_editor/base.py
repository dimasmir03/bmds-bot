from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ImageEditOptions(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class ImageOutput(BaseModel):
    path: Path
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImageEditResult(BaseModel):
    success: bool
    provider: str
    outputs: list[ImageOutput] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ImageEditorProvider(ABC):
    name: str

    async def startup(self) -> None:
        """Load heavy resources (e.g. model weights) before the first job."""
        return None

    @abstractmethod
    async def edit(
        self,
        input_path: Path,
        prompt: str,
        output_path: Path,
        options: ImageEditOptions | None = None,
    ) -> ImageEditResult:
        raise NotImplementedError
