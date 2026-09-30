from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @field_validator("image_provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
