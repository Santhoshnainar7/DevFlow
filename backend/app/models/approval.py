"""
Domain models and schemas for the DevFlow Human Approval Workflow.

Defines approval decisions, requests, actions, and validation results.
Ensures human authorization is explicit, verifiable, and immutable.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ApprovalDecision(str, Enum):
    """Lifecycle states and decisions for a human approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ApprovalRequest(BaseModel):
    """
    Persistent record of a proposed fix requiring human developer approval.
    """

    approval_id: str
    issue_id: str
    issue_title: str
    root_cause: str
    affected_files: List[str] = Field(default_factory=list)
    proposed_fix: str
    testing_plan: List[str] = Field(default_factory=list)
    status: ApprovalDecision = ApprovalDecision.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    def is_expired(self) -> bool:
        """Returns True if the approval request has exceeded its expiration timestamp."""
        now = datetime.now(timezone.utc)
        return now > self.expires_at

    def to_switch_prompt(self) -> str:
        """
        Formats the message for Switch team chat following the required format.
        """
        affected = ", ".join(self.affected_files) if self.affected_files else "None"
        plan_bullets = (
            "\n".join(f"- {p}" for p in self.testing_plan)
            if self.testing_plan
            else "- Automated regression suite"
        )

        return (
            f"Investigation completed.\n\n"
            f"Issue: {self.issue_id}\n"
            f"Root cause: {self.root_cause}\n"
            f"Affected file: {affected}\n\n"
            f"Proposed fix:\n{self.proposed_fix}\n\n"
            f"Testing plan:\n{plan_bullets}\n\n"
            f"Reply with:\n\n"
            f"APPROVE {self.issue_id}\n"
            f"or\n"
            f"REJECT {self.issue_id}"
        )


class ApprovalActionPayload(BaseModel):
    """Chat message action submitted by a user in team chat or via API."""

    raw_command: str  # e.g., "APPROVE DF-001" or "REJECT DF-001"
    user_id: str
    issue_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApprovalValidationResult(BaseModel):
    """
    Server-side validation outcome.
    'execution_permitted' is strictly True ONLY if valid approval was granted.
    """

    is_valid: bool
    decision: ApprovalDecision
    approval_id: str
    issue_id: str
    decided_by: str
    execution_permitted: bool
    message: str
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    execution_token: Optional[str] = None  # Ephemeral single-use token for execution gate

