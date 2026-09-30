from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PROMPT_TEMPLATE = (
    "Change only the person's clothing to: {request}. Keep the person's face, identity, "
    "hairstyle, body shape, pose, lighting and background unchanged."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    telegram_bot_token: str = ""
    database_url: str = "postgresql+asyncpg://bmds:bmds@localhost:5432/bmds"
    redis_url: str = "redis://localhost:6379/0"
    admin_api_key: str = Field(default="change-me", min_length=1)
    image_provider: str = "mock"
    storage_root: Path = Path("storage")
    max_image_size_mb: int = Field(default=20, gt=0)
    log_level: str = "INFO"
    mock_processing_delay_seconds: float = Field(default=2.0, ge=0)
    max_concurrent_jobs: int = Field(default=1, ge=1)
    rate_limit_jobs: int = Field(default=5, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    redis_queue_name: str = "image_jobs"

    hf_model_id: str = "black-forest-labs/FLUX.2-klein-9B"
    hf_token: str = ""
    model_device: str = "cuda"
    model_cpu_offload: bool = False
    model_quantization: Literal["none", "8bit", "4bit"] = "none"
    model_num_inference_steps: int = Field(default=4, ge=1)
    model_guidance_scale: float = Field(default=1.0, ge=0)
    model_max_image_side: int = Field(default=1024, ge=256, le=2048)
    model_seed: int | None = None
    model_prompt_template: str = DEFAULT_PROMPT_TEMPLATE

    @field_validator("image_provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("model_prompt_template")
    @classmethod
    def validate_prompt_template(cls, value: str) -> str:
        if "{request}" not in value:
            raise ValueError("MODEL_PROMPT_TEMPLATE must contain {request}")
        try:
            value.format(request="")
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f"Invalid MODEL_PROMPT_TEMPLATE: {exc}") from exc
        return value

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
