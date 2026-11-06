"""
Centralized configuration management for DevFlow.

Loads environment variables from .env and validates them with Pydantic.
Provides type safety, default fallbacks, and clear validation error messages.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

from dotenv import dotenv_values
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """Application settings validated against environment variables."""

    # Project metadata
    PROJECT_NAME: str = "DevFlow"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # Gemini LLM configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Switch agent platform connection
    SWITCH_AGENT_TOKEN: Optional[str] = None
    SWITCH_SERVER_URL: str = "http://localhost:3000"
    SWITCH_AGENT_ID: Optional[str] = None
    DEVFLOW_AGENT_NAME: str = "devflow"

    # Security & Execution limits
    DEVFLOW_APPROVED_USERS: List[str] = Field(default_factory=list)
    DEVFLOW_APPROVAL_TIMEOUT_SECONDS: int = 300
    DEVFLOW_TEST_TIMEOUT_SECONDS: int = 60
    DEVFLOW_REPO_PATH: Path = Field(
        default_factory=lambda: Path(os.getcwd()) / "demo_repository"
    )
    DEVFLOW_FIX_BRANCH_PREFIX: str = "devflow/fix"

    @field_validator("PORT")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be between 1 and 65535, got {v}")
        return v

    @field_validator("DEVFLOW_APPROVAL_TIMEOUT_SECONDS", "DEVFLOW_TEST_TIMEOUT_SECONDS")
    @classmethod
    def validate_positive_timeout(cls, v: int, info) -> int:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be greater than 0, got {v}")
        return v

    @field_validator("DEVFLOW_APPROVED_USERS", mode="before")
    @classmethod
    def parse_approved_users(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [user.strip() for user in v.split(",") if user.strip()]
        return v or []

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}, got '{v}'")
        return upper_v


def load_settings(env_file_path: Optional[Path] = None) -> Settings:
    """
    Constructs a Settings instance by merging:
    1. Default values in Settings
    2. Key-values from .env (if present)
    3. OS environment variables (highest priority)
    """
    target_env = env_file_path or (Path(os.getcwd()) / ".env")
    env_file_vars = {}
    if target_env.exists():
        env_file_vars = {k: v for k, v in dotenv_values(target_env).items() if v is not None}

    # Overlay with process environment variables
    merged_vars = {**env_file_vars, **os.environ}
    return Settings(**{k: v for k, v in merged_vars.items() if k in Settings.model_fields})


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton accessor for application settings."""
    return load_settings()

