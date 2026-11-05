"""
Centralized exception handling for DevFlow.

Defines custom domain exceptions and provides FastAPI exception handlers
that convert errors into consistent, structured JSON responses.
"""

from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("exceptions")


class DevFlowBaseException(Exception):
    """Base exception for all domain-specific DevFlow errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "DEVFLOW_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class ConfigurationError(DevFlowBaseException):
    """Raised when environment or startup configuration is invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class UnauthorizedApproverError(DevFlowBaseException):
    """Raised when a user without approval permissions attempts to approve/reject a fix."""

    def __init__(self, user: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"User '{user}' is not authorized to approve DevFlow fixes.",
            error_code="UNAUTHORIZED_APPROVER",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"user": user, **(details or {})},
        )


class WorkflowStateError(DevFlowBaseException):
    """Raised when an invalid state transition is requested."""

    def __init__(self, message: str, current_state: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="INVALID_WORKFLOW_STATE",
            status_code=status.HTTP_409_CONFLICT,
            details={"current_state": current_state, **(details or {})},
        )


class RepositoryError(DevFlowBaseException):
    """Raised when git inspection or repository operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="REPOSITORY_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class ExecutionTimeoutError(DevFlowBaseException):
    """Raised when a subprocess execution exceeds its hard timeout."""

    def __init__(self, command: str, timeout_seconds: int):
        super().__init__(
            message=f"Execution of command '{command}' timed out after {timeout_seconds}s.",
            error_code="EXECUTION_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details={"command": command, "timeout_seconds": timeout_seconds},
        )


# ---------------------------------------------------------------------------
# FastAPI Global Exception Handlers
# ---------------------------------------------------------------------------

async def devflow_exception_handler(request: Request, exc: DevFlowBaseException) -> JSONResponse:
    """Handles all DevFlow domain exceptions with consistent JSON formatting."""
    logger.warning(
        f"Domain exception [{exc.error_code}]: {exc.message} on {request.method} {request.url.path}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles FastAPI/Pydantic request validation errors."""
    logger.info(f"Request validation failed on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "Input validation failed.",
            "details": {"errors": exc.errors()},
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled internal server errors."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal server error occurred.",
            "details": {},
        },
    )

