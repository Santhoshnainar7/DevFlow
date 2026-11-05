"""
Pytest configuration and shared fixtures for DevFlow tests.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path so 'app' is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Fixture providing isolated settings for testing."""
    return Settings(
        PROJECT_NAME="DevFlow-Test",
        VERSION="0.1.0-test",
        ENVIRONMENT="test",
        PORT=8001,
        LOG_LEVEL="DEBUG",
        DEVFLOW_APPROVED_USERS=["tester1", "tester2"],
        DEVFLOW_APPROVAL_TIMEOUT_SECONDS=60,
        DEVFLOW_TEST_TIMEOUT_SECONDS=30,
    )


@pytest.fixture
def app(test_settings: Settings):
    """Fixture providing a fresh FastAPI application instance."""
    return create_app(custom_settings=test_settings)


@pytest.fixture
def client(app) -> TestClient:
    """Fixture providing a TestClient for testing HTTP endpoints."""
    return TestClient(app, raise_server_exceptions=False)

