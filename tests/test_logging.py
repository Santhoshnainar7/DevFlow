"""
Tests for structured logging formatting and configuration.
"""

import json
import logging

from app.core.logging import StructuredJsonFormatter, StructuredTextFormatter, get_logger, setup_logging


def test_structured_json_formatter():
    """Verify JSON formatter produces parseable JSON with required fields."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="devflow.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test event occurred",
        args=(),
        exc_info=None,
    )
    record.room_id = "room-123"

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "devflow.test"
    assert parsed["message"] == "Test event occurred"
    assert parsed["room_id"] == "room-123"
    assert "timestamp" in parsed


def test_structured_text_formatter():
    """Verify structured text formatter includes bracketed metadata."""
    formatter = StructuredTextFormatter()
    record = logging.LogRecord(
        name="devflow.test",
        level=logging.WARNING,
        pathname="test.py",
        lineno=10,
        msg="Warning event",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "[WARNING ]" in formatted
    assert "[devflow.test]" in formatted
    assert "Warning event" in formatted


def test_get_logger_prefix():
    """Verify get_logger namespaces loggers under 'devflow'."""
    log1 = get_logger("workflow")
    assert log1.name == "devflow.workflow"

    log2 = get_logger("devflow.custom")
    assert log2.name == "devflow.custom"

