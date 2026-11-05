"""
DevFlow Backend Application Entrypoint.

Initializes FastAPI with structured logging, centralized exception handlers,
and the core health check endpoints.
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    DevFlowBaseException,
    devflow_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.models.health import HealthResponse

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown lifecycle."""
    settings = get_settings()
    setup_logging(level=settings.LOG_LEVEL, json_format=settings.LOG_JSON)
    logger.info(
        f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]"
    )
    yield
    logger.info(f"Stopping {settings.PROJECT_NAME}")


def create_app(custom_settings: Settings | None = None) -> FastAPI:
    """Application factory for DevFlow."""
    settings = custom_settings or get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Switch-connected autonomous bug investigation and fix agent.",
        lifespan=lifespan,
    )

    # -----------------------------------------------------------------------
    # Exception Handlers
    # -----------------------------------------------------------------------
    app.add_exception_handler(DevFlowBaseException, devflow_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # -----------------------------------------------------------------------
    # Middleware: Request Logging & Latency Tracking
    # -----------------------------------------------------------------------
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms)"
        )
        return response

    # -----------------------------------------------------------------------
    # Health Check & Root Endpoints
    # -----------------------------------------------------------------------
    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Service Health Check",
        tags=["System"],
    )
    async def health_check() -> HealthResponse:
        """Returns the operational status, version, and environment of DevFlow."""
        return HealthResponse(
            status="ok",
            app_name=settings.PROJECT_NAME,
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
        )

    @app.get("/", summary="API Root", tags=["System"])
    async def root():
        """Root endpoint returning basic service info."""
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "operational",
            "docs_url": "/docs",
        }

    return app


# Default ASGI application instance
app = create_app()

