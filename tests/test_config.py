"""
Tests for configuration loading and validation in app.core.config.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_settings():
    """Verify default configuration values."""
    settings = Settings()
    assert settings.PROJECT_NAME == "DevFlow"
    assert settings.PORT == 8000
    assert settings.ENVIRONMENT == "development"
    assert settings.DEVFLOW_APPROVAL_TIMEOUT_SECONDS == 300
    assert settings.DEVFLOW_TEST_TIMEOUT_SECONDS == 60


def test_port_validation():
    """Verify invalid port numbers raise validation errors."""
    with pytest.raises(ValidationError):
        Settings(PORT=0)

    with pytest.raises(ValidationError):
        Settings(PORT=70000)

    valid = Settings(PORT=9000)
    assert valid.PORT == 9000


def test_timeout_validation():
    """Verify non-positive timeouts raise validation errors."""
    with pytest.raises(ValidationError):
        Settings(DEVFLOW_APPROVAL_TIMEOUT_SECONDS=0)

    with pytest.raises(ValidationError):
        Settings(DEVFLOW_TEST_TIMEOUT_SECONDS=-10)


def test_approved_users_parsing():
    """Verify comma-separated string is parsed into a list."""
    settings = Settings(DEVFLOW_APPROVED_USERS="alice, bob, charlie")
    assert settings.DEVFLOW_APPROVED_USERS == ["alice", "bob", "charlie"]


def test_log_level_validation():
    """Verify invalid log level raises validation error."""
    with pytest.raises(ValidationError):
        Settings(LOG_LEVEL="INVALID_LEVEL")

    valid = Settings(LOG_LEVEL="debug")
    assert valid.LOG_LEVEL == "DEBUG"

