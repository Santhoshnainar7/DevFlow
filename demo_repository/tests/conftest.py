import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Provides a FastAPI TestClient for all tests."""
    return TestClient(app)


@pytest.fixture
def valid_credentials() -> dict:
    """A known-good username/password pair from the in-memory user store."""
    return {"username": "alice", "password": "password123"}

