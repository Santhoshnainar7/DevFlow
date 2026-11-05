"""
Pydantic schemas for service health and standard responses.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema returned by the /health endpoint."""

    status: str = "ok"
    app_name: str
    version: str
    environment: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApiResponse(BaseModel):
    """Generic wrapper for standard API responses."""

    success: bool = True
    message: str = "Success"
    data: Optional[Dict[str, Any]] = None

