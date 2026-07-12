from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings


class HealthResponse(BaseModel):
    """Response returned by the API health endpoint."""

    status: Literal["healthy"]
    service: str
    version: str
    environment: str


router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the current API health status."""

    settings = get_settings()

    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
