import asyncio
import shutil
from pathlib import Path

from app.providers.image_editor.base import (
    ImageEditOptions,
    ImageEditorProvider,
    ImageEditResult,
    ImageOutput,
)


class MockImageEditorProvider(ImageEditorProvider):
    name = "mock"

    def __init__(self, delay_seconds: float = 2.0) -> None:
        self.delay_seconds = delay_seconds

    async def edit(
        self,
        input_path: Path,
        prompt: str,
        output_path: Path,
        options: ImageEditOptions | None = None,
    ) -> ImageEditResult:
        if not await asyncio.to_thread(input_path.is_file):
            raise FileNotFoundError(f"Input image does not exist: {input_path}")
        await asyncio.sleep(self.delay_seconds)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copyfile, input_path, output_path)
        return ImageEditResult(
            success=True,
            provider=self.name,
            outputs=[ImageOutput(path=output_path)],
            metadata={"mock": True, "prompt_length": len(prompt)},
        )
