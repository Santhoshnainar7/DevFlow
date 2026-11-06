"""
Domain models and schemas for DevFlow Phase 05: Controlled Code Fixing and Test Execution.

Defines fix patches, execution plans, status enums, and structured execution reports.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Status outcomes for a fix execution run."""

    SUCCESS = "SUCCESS"
    FAILED_TESTS = "FAILED_TESTS"
    FAILED_DIRTY_REPO = "FAILED_DIRTY_REPO"
    FAILED_UNAUTHORIZED_FILE = "FAILED_UNAUTHORIZED_FILE"
    FAILED_INVALID_APPROVAL = "FAILED_INVALID_APPROVAL"
    FAILED_TIMEOUT = "FAILED_TIMEOUT"
    FAILED_DEPENDENCY = "FAILED_DEPENDENCY"
    FAILED_ERROR = "FAILED_ERROR"


class FixPatch(BaseModel):
    """A targeted code patch for a single file within the authorized workspace."""

    relative_path: str  # e.g., "app/routers/auth.py"
    new_content: str
    description: str = ""


class FixPlan(BaseModel):
    """Specification of an approved bug fix ready for controlled execution."""

    issue_id: str
    approval_id: str
    execution_token: str
    patches: List[FixPatch] = Field(default_factory=list)
    target_tests: List[str] = Field(default_factory=list)
    summary_of_changes: str = ""
    timeout_seconds: Optional[int] = None


class ExecutionReport(BaseModel):
    """
    Standardized execution report generated after attempting code modification and test runs.
    Follows the exact specification required by DevFlow Phase 05.
    """

    issue_id: str
    approval_id: str
    branch: str
    files_changed: List[str] = Field(default_factory=list)
    changes_made: str
    tests_executed: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    execution_status: ExecutionStatus
    remaining_risks: str
    diff: Optional[str] = None
    test_output: Optional[str] = None
    error_details: Optional[str] = None
    requires_human_intervention: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_formatted_report(self) -> str:
        """Renders the execution report string matching the required prompt specification."""
        files = ", ".join(self.files_changed) if self.files_changed else "None"
        lines = [
            f"Issue ID: {self.issue_id}",
            f"Approval ID: {self.approval_id}",
            f"Branch: {self.branch}",
            f"Files changed: {files}",
            f"Changes made: {self.changes_made}",
            f"Tests executed: {self.tests_executed}",
            f"Tests passed: {self.tests_passed}",
            f"Tests failed: {self.tests_failed}",
            f"Execution status: {self.execution_status.value}",
            f"Remaining risks: {self.remaining_risks}",
        ]
        if self.diff:
            lines.append(f"\n--- Code Diff ---\n{self.diff.strip()}")
        if self.error_details:
            lines.append(f"\n--- Error Details ---\n{self.error_details.strip()}")
        if self.requires_human_intervention:
            lines.append("\n[ACTION REQUIRED]: Automated fix requires human developer intervention.")

        return "\n".join(lines)

