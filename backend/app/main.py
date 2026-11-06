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
from app.models.approval import (
    ApprovalActionPayload,
    ApprovalRequest,
    ApprovalValidationResult,
)
from app.models.health import HealthResponse
from app.models.investigation import InvestigationReport, InvestigationRequest
from app.services.approval_manager import approval_manager
from app.services.investigation_engine import BugInvestigationEngine

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

    # -----------------------------------------------------------------------
    # Bug Investigation Engine Endpoints
    # -----------------------------------------------------------------------
    engine = BugInvestigationEngine(default_repo_path=settings.DEVFLOW_REPO_PATH)

    @app.post(
        "/api/v1/investigate",
        response_model=InvestigationReport,
        summary="Investigate Bug",
        tags=["Investigation"],
    )
    async def investigate_bug(request: InvestigationRequest) -> InvestigationReport:
        """
        Executes an automated, read-only bug investigation on the connected repository.
        Returns the structured 11-field investigation report.
        """
        return engine.investigate(request)

    @app.post(
        "/api/v1/investigate/formatted",
        summary="Investigate Bug (Formatted Text)",
        tags=["Investigation"],
    )
    async def investigate_bug_formatted(request: InvestigationRequest) -> Response:
        """
        Executes bug investigation and returns the report in plain-text markdown format
        matching the Switch chat requirements.
        """
        report = engine.investigate(request)
        return Response(content=report.to_formatted_report(), media_type="text/plain")

    # -----------------------------------------------------------------------
    # Human Approval Workflow Endpoints
    # -----------------------------------------------------------------------
    @app.post(
        "/api/v1/approvals/decide",
        response_model=ApprovalValidationResult,
        summary="Process Approval Decision",
        tags=["Approval"],
    )
    async def process_approval_decision(
        payload: ApprovalActionPayload,
    ) -> ApprovalValidationResult:
        """
        Validates developer approval or rejection action.
        Only grants execution token if authorized user submits valid command.
        """
        return approval_manager.process_action(payload)

    @app.get(
        "/api/v1/approvals/{issue_id}",
        response_model=ApprovalRequest,
        summary="Get Approval Request Status",
        tags=["Approval"],
    )
    async def get_approval_status(issue_id: str) -> ApprovalRequest:
        """Retrieves persistent approval status for an issue."""
        req = approval_manager.get_request(issue_id)
        if not req:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"No approval request for issue '{issue_id}'.")
        return req

    return app


# Default ASGI application instance
app = create_app()

