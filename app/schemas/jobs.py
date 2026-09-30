import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.image_job import JobStatus


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    telegram_chat_id: int
    prompt: str
    provider: str
    status: JobStatus
    error_message: str | None
    cancel_requested: bool
    parent_job_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
