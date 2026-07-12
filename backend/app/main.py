from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the SafeOps AI FastAPI application."""

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend API for SafeOps AI, a guardrailed agentic "
            "incident investigation and response platform."
        ),
        debug=settings.debug,
    )

    application.include_router(
        health_router,
        prefix=settings.api_v1_prefix,
    )

    @application.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        """Return basic API information."""

        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "documentation": "/docs",
        }

    return application


app = create_app()
