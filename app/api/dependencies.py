from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import Settings, get_settings


async def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    settings: Settings = get_settings()
    if x_api_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
