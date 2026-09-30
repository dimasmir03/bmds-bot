from fastapi import FastAPI

from app.api.routes import health, jobs
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="BMDS Bot API", version="0.1.0")
app.include_router(health.router)
app.include_router(jobs.router)
