"""
Issue tracking service for DevFlow.

Provides sequential, unique issue identifiers (e.g., DF-001, DF-002)
with thread safety across concurrent triage requests.
"""

import threading
from typing import Dict


class IssueTracker:
    """Thread-safe sequential issue identifier generator."""

    def __init__(self, prefix: str = "DF"):
        self.prefix = prefix
        self._counters: Dict[str, int] = {}
        self._lock = threading.Lock()

    def generate_id(self, scope: str = "default") -> str:
        """Generates the next sequential issue ID for a given room or scope."""
        with self._lock:
            current = self._counters.get(scope, 0) + 1
            self._counters[scope] = current
            return f"{self.prefix}-{current:03d}"

    def get_current(self, scope: str = "default") -> int:
        """Returns the current counter for a scope without incrementing."""
        with self._lock:
            return self._counters.get(scope, 0)

    def reset(self, scope: str = "default"):
        """Resets the counter for testing purposes."""
        with self._lock:
            self._counters[scope] = 0


# Global singleton instance
issue_tracker = IssueTracker()

