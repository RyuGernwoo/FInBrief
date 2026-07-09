"""FastAPI entrypoint for FinBrief."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()

    app = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        description="FinBrief personalized AI financial briefing API",
    )
    app.include_router(api_router, prefix=runtime_settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": "finbrief",
            "health": f"{runtime_settings.api_v1_prefix}/health",
            "docs": "/docs",
        }

    return app


app = create_app()
