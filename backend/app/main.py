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
from app.models.execution import ExecutionReport, FixPlan
from app.models.health import HealthResponse
from app.models.investigation import InvestigationReport, InvestigationRequest
from app.models.reporting import EngineeringReport, GitHubReference, StageUpdate
from app.services.approval_manager import approval_manager
from app.services.engineering_reporter import engineering_reporter
from app.services.fix_executor import FixExecutor
from app.services.github_service import github_service
from app.services.investigation_engine import BugInvestigationEngine
from app.services.switch_reporter import switch_reporter

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

    # -----------------------------------------------------------------------
    # Controlled Code Fixing & Test Execution Endpoints
    # -----------------------------------------------------------------------
    executor = FixExecutor(
        repo_path=settings.DEVFLOW_REPO_PATH,
        manager=approval_manager,
        test_timeout_seconds=settings.DEVFLOW_TEST_TIMEOUT_SECONDS,
    )

    @app.post(
        "/api/v1/fixes/execute",
        response_model=ExecutionReport,
        summary="Execute Approved Fix",
        tags=["Execution"],
    )
    async def execute_approved_fix(plan: FixPlan) -> ExecutionReport:
        """
        Applies an approved bug fix on an isolated branch and validates with tests.
        Reverts changes if tests fail and blocks execution without valid approval token.
        """
        return executor.execute_fix(plan)

    @app.post(
        "/api/v1/fixes/execute/formatted",
        summary="Execute Approved Fix (Formatted Text)",
        tags=["Execution"],
    )
    async def execute_approved_fix_formatted(plan: FixPlan) -> Response:
        """
        Executes approved fix and returns report formatted for team chat.
        """
        report = executor.execute_fix(plan)
        return Response(content=report.to_formatted_report(), media_type="text/plain")

    # -----------------------------------------------------------------------
    # Engineering Reporting & GitHub Integration Endpoints
    # -----------------------------------------------------------------------
    @app.get(
        "/api/v1/reporting/stages/{issue_id}",
        response_model=list[StageUpdate],
        summary="Get Workflow Stage Updates",
        tags=["Reporting"],
    )
    async def get_stage_updates(issue_id: str) -> list[StageUpdate]:
        """Retrieves all chronological stage notifications recorded for an issue."""
        return switch_reporter.get_updates(issue_id)

    @app.post(
        "/api/v1/github/create-issue",
        response_model=GitHubReference,
        summary="Create GitHub Issue",
        tags=["GitHub"],
    )
    async def create_github_issue(
        issue_id: str,
        title: str,
        body: str,
        room_id: str | None = None,
        is_approved: bool = True,
    ) -> GitHubReference:
        """Creates a tracking issue on GitHub for an approved bug report."""
        return github_service.create_issue(
            issue_id=issue_id,
            title=title,
            body=body,
            switch_room=room_id,
            is_approved=is_approved,
        )

    @app.post(
        "/api/v1/github/create-pr",
        response_model=GitHubReference,
        summary="Create GitHub Pull Request",
        tags=["GitHub"],
    )
    async def create_github_pr(
        issue_id: str,
        title: str,
        head_branch: str,
        body: str,
        base_branch: str = "main",
        is_approved: bool = True,
    ) -> GitHubReference:
        """Prepares a pull request for human developer review."""
        return github_service.create_pull_request(
            issue_id=issue_id,
            title=title,
            head_branch=head_branch,
            body=body,
            base_branch=base_branch,
            is_approved=is_approved,
        )

    return app


# Default ASGI application instance
app = create_app()

