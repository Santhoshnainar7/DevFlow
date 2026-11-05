"""
Structured logging module for DevFlow.

Provides JSON and human-readable structured formatters with timestamps,
log levels, logger names, and contextual fields (e.g., room_id, correlation_id).
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include standard exception info if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include custom extra context if provided
        for key in ("room_id", "session_id", "author_id", "request_id", "step"):
            if hasattr(record, key):
                log_payload[key] = getattr(record, key)

        return json.dumps(log_payload)


class StructuredTextFormatter(logging.Formatter):
    """Formats log records with consistent bracketed metadata."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{record.levelname:<8}] [{record.name}]"
        
        # Optional context
        extras = []
        for key in ("room_id", "session_id", "step"):
            if hasattr(record, key):
                extras.append(f"{key}={getattr(record, key)}")
        context_str = f" ({', '.join(extras)})" if extras else ""

        message = f"{prefix}{context_str} {record.getMessage()}"
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        return message


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configures the root and devflow loggers with structured formatters."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to prevent duplicate lines
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    formatter = StructuredJsonFormatter() if json_format else StructuredTextFormatter()
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Returns a logger namespaced under devflow."""
    if name:
        logger_name = f"devflow.{name}" if not name.startswith("devflow") else name
    else:
        logger_name = "devflow"
    return logging.getLogger(logger_name)

