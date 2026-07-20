from fastapi import FastAPI

from app.api.routes.health import (
    router as health_router,
)
from app.api.routes.rag import (
    router as rag_router,
)
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the SafeOps FastAPI application."""

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description=(
            "Guardrailed incident investigation and "
            "operational knowledge API."
        ),
    )

    @application.get(
        "/",
        tags=["System"],
        summary="Get API information",
    )
    def root() -> dict[str, str]:
        """Return basic SafeOps API information."""

        return {
            "name": settings.app_name,
            "status": "running",
            "version": settings.app_version,
            "environment": settings.environment,
            "documentation": "/docs",
        } 

    application.include_router(
        health_router,
        prefix=settings.api_v1_prefix,
    )

    application.include_router(
        rag_router,
        prefix=settings.api_v1_prefix,
    )

    return application


app = create_app()