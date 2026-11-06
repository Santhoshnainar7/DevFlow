"""
Domain models and schemas for DevFlow Phase 06: Engineering Reporting and GitHub Integration.

Defines the 8 Switch workflow reporting stages, GitHub references,
stage updates, and the structured final engineering report.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowStage(str, Enum):
    """The 8 standardized workflow communication stages for Switch chat updates."""

    BUG_RECEIVED = "BUG_RECEIVED"
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    INVESTIGATION_COMPLETED = "INVESTIGATION_COMPLETED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_DECIDED = "APPROVAL_DECIDED"
    FIX_IMPLEMENTATION_STARTED = "FIX_IMPLEMENTATION_STARTED"
    TESTS_COMPLETED = "TESTS_COMPLETED"
    FINAL_REPORT_PUBLISHED = "FINAL_REPORT_PUBLISHED"


class StageUpdate(BaseModel):
    """A concise, structured communication message for a specific workflow stage."""

    stage: WorkflowStage
    issue_id: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    room_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GitHubReference(BaseModel):
    """Metadata tracking associated GitHub issues, pull requests, and branch references."""

    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    head_branch: Optional[str] = None
    base_branch: str = "main"
    status: str = "none"  # "created", "pr_opened", "disabled", "unconfigured"


class EngineeringReport(BaseModel):
    """
    Standardized final engineering report for developers and stakeholders.
    Combines diagnosis, approval audit, code changes, actual test results,
    and external GitHub references.
    """

    issue_id: str
    approval_id: str
    description: str
    root_cause: str
    proposed_solution: str
    implemented_solution: str
    files_changed: List[str] = Field(default_factory=list)
    branch: str
    tests_executed: int
    tests_passed: int
    tests_failed: int
    execution_status: str
    remaining_risks: str
    github: Optional[GitHubReference] = None
    diff: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_formatted_report(self) -> str:
        """Renders the comprehensive engineering report matching the exact Phase 06 specification."""
        files = ", ".join(self.files_changed) if self.files_changed else "None"
        github_ref = "None configured (offline mode)"
        if self.github and (self.github.issue_url or self.github.pr_url):
            refs = []
            if self.github.issue_url:
                refs.append(f"Issue #{self.github.issue_number} ({self.github.issue_url})")
            if self.github.pr_url:
                refs.append(f"PR #{self.github.pr_number} ({self.github.pr_url})")
            github_ref = ", ".join(refs)

        test_summary = f"{self.tests_passed} passed, {self.tests_failed} failed ({self.execution_status})"

        lines = [
            f"Issue identifier: {self.issue_id}",
            f"Problem description: {self.description}",
            f"Root cause: {self.root_cause}",
            f"Proposed solution: {self.proposed_solution}",
            f"Implemented solution: {self.implemented_solution}",
            f"Files changed: {files}",
            f"Tests executed: {self.tests_executed}",
            f"Actual test results: {test_summary}",
            f"Git branch: {self.branch}",
            f"Remaining risks: {self.remaining_risks}",
            f"GitHub references: {github_ref}",
        ]

        if self.diff:
            lines.append(f"\n--- Code Diff ---\n{self.diff.strip()}")

        return "\n".join(lines)

