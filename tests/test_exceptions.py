"""
Tests for centralized exception handling and structured error responses.
"""

from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.exceptions import (
    ConfigurationError,
    ExecutionTimeoutError,
    RepositoryError,
    UnauthorizedApproverError,
    WorkflowStateError,
)
from app.main import create_app


def test_custom_exception_properties():
    """Verify custom exception serialization and status code assignment."""
    exc = UnauthorizedApproverError("malicious_user")
    assert exc.status_code == 403
    assert exc.error_code == "UNAUTHORIZED_APPROVER"
    assert "malicious_user" in exc.message

    timeout_exc = ExecutionTimeoutError("pytest tests/", 60)
    assert timeout_exc.status_code == 504
    assert timeout_exc.details["timeout_seconds"] == 60


def test_exception_handler_integration():
    """Verify centralized exception handler catches domain errors and formats JSON."""
    test_router = APIRouter()

    @test_router.get("/test-unauthorized")
    def trigger_unauthorized():
        raise UnauthorizedApproverError("unapproved_bob")

    @test_router.get("/test-conflict")
    def trigger_conflict():
        raise WorkflowStateError("Cannot approve from idle", current_state="IDLE")

    @test_router.get("/test-unhandled")
    def trigger_unhandled():
        raise RuntimeError("Something unexpectedly broke!")

    class DummyPayload(BaseModel):
        required_field: str

    @test_router.post("/test-validation")
    def trigger_validation(payload: DummyPayload):
        return {"status": "ok"}

    app = create_app(custom_settings=Settings(ENVIRONMENT="test"))
    app.include_router(test_router)
    client = TestClient(app, raise_server_exceptions=False)

    # 1. Domain exception -> 403
    res_auth = client.get("/test-unauthorized")
    assert res_auth.status_code == 403
    body_auth = res_auth.json()
    assert body_auth["success"] is False
    assert body_auth["error_code"] == "UNAUTHORIZED_APPROVER"
    assert "unapproved_bob" in body_auth["message"]

    # 2. Domain exception -> 409
    res_conflict = client.get("/test-conflict")
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error_code"] == "INVALID_WORKFLOW_STATE"

    # 3. Unhandled runtime error -> 500
    res_unhandled = client.get("/test-unhandled")
    assert res_unhandled.status_code == 500
    assert res_unhandled.json()["error_code"] == "INTERNAL_SERVER_ERROR"

    # 4. Request validation error -> 422
    res_val = client.post("/test-validation", json={})
    assert res_val.status_code == 422
    assert res_val.json()["error_code"] == "VALIDATION_ERROR"

