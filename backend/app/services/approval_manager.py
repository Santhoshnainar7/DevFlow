"""
Human Approval Workflow Service for DevFlow.

Enforces server-side permission controls, handles approval lifecycle,
prevents duplicate/unauthorized/expired executions, and persists approval states.
"""

import json
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedApproverError, WorkflowStateError
from app.core.logging import get_logger
from app.models.approval import (
    ApprovalActionPayload,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalValidationResult,
)

logger = get_logger("approval_manager")


class ApprovalManager:
    """Manages the full human approval lifecycle with persistent storage and strict security."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        authorized_users: Optional[List[str]] = None,
        default_timeout_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.storage_path = storage_path or (Path(settings.DEVFLOW_REPO_PATH).parent / "data" / "approvals.json")
        self.authorized_users = (
            [u.lower().lstrip("@").strip() for u in authorized_users]
            if authorized_users is not None
            else [u.lower().lstrip("@").strip() for u in settings.DEVFLOW_APPROVED_USERS]
        )
        self.default_timeout_seconds = (
            default_timeout_seconds
            if default_timeout_seconds is not None
            else settings.DEVFLOW_APPROVAL_TIMEOUT_SECONDS
        )

        self._requests: Dict[str, ApprovalRequest] = {}  # keyed by issue_id
        self._consumed_tokens: set[str] = set()
        self._active_tokens: Dict[str, str] = {}  # issue_id -> token
        self._lock = threading.Lock()

        self._load_from_disk()

    # -----------------------------------------------------------------------
    # Authorization & Permission Controls
    # -----------------------------------------------------------------------

    def is_user_authorized(self, user_id: str) -> bool:
        """
        Server-side validation: Verifies user exists in the configured allowlist.
        Case-insensitive and normalizes @mentions.
        """
        clean_user = user_id.lower().lstrip("@").strip()
        if not clean_user:
            return False

        # If allowlist configured, must be an exact match
        if self.authorized_users:
            is_allowed = clean_user in self.authorized_users
            logger.info(f"Authorization check for user '{user_id}' ({clean_user}): {is_allowed}")
            return is_allowed

        # If no allowlist configured in development mode, log warning
        logger.warning(f"No authorized users configured in DEVFLOW_APPROVED_USERS. Denying '{user_id}'.")
        return False

    def add_authorized_user(self, user_id: str):
        """Dynamically registers an authorized user."""
        with self._lock:
            clean = user_id.lower().lstrip("@").strip()
            if clean and clean not in self.authorized_users:
                self.authorized_users.append(clean)

    # -----------------------------------------------------------------------
    # Request Creation & Expiration
    # -----------------------------------------------------------------------

    def create_request(
        self,
        issue_id: str,
        issue_title: str,
        root_cause: str,
        affected_files: List[str],
        proposed_fix: str,
        testing_plan: List[str],
        timeout_seconds: Optional[int] = None,
    ) -> ApprovalRequest:
        """
        Generates and persists a new ApprovalRequest with a unique approval ID.
        """
        with self._lock:
            timeout = timeout_seconds or self.default_timeout_seconds
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=timeout)
            approval_id = f"APP-{issue_id}-{secrets.token_hex(4).upper()}"

            req = ApprovalRequest(
                approval_id=approval_id,
                issue_id=issue_id,
                issue_title=issue_title,
                root_cause=root_cause,
                affected_files=affected_files,
                proposed_fix=proposed_fix,
                testing_plan=testing_plan,
                status=ApprovalDecision.PENDING,
                created_at=now,
                expires_at=expires_at,
            )

            self._requests[issue_id] = req
            self._save_to_disk()
            logger.info(f"Created approval request {approval_id} for issue {issue_id} (expires in {timeout}s)")
            return req

    def get_request(self, issue_id: str) -> Optional[ApprovalRequest]:
        """Retrieves an approval request by issue identifier."""
        with self._lock:
            return self._requests.get(issue_id)

    def cancel_request(self, issue_id: str, cancelled_by: str, reason: str = "Cancelled by user") -> bool:
        """Explicitly cancels an approval request, prohibiting future approvals."""
        with self._lock:
            req = self._requests.get(issue_id)
            if not req:
                return False

            req.status = ApprovalDecision.CANCELLED
            req.decided_by = cancelled_by
            req.decided_at = datetime.now(timezone.utc)
            req.rejection_reason = reason
            self._save_to_disk()
            logger.info(f"Issue {issue_id} approval request cancelled by {cancelled_by}: {reason}")
            return True

    # -----------------------------------------------------------------------
    # Processing Approval / Rejection Actions
    # -----------------------------------------------------------------------

    def process_action(self, payload: ApprovalActionPayload) -> ApprovalValidationResult:
        """
        Validates chat command action with strict server-side permission controls.
        Enforces:
        - Explicit syntax ("APPROVE <issue_id>" or "REJECT <issue_id>")
        - Active pending state (no duplicates, no expired, no cancelled)
        - Authorized user identity
        """
        with self._lock:
            # 1. Parse command syntax
            parsed = self._parse_command(payload.raw_command)
            if not parsed:
                return ApprovalValidationResult(
                    is_valid=False,
                    decision=ApprovalDecision.PENDING,
                    approval_id="UNKNOWN",
                    issue_id=payload.issue_id or "UNKNOWN",
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=(
                        f"Invalid approval command syntax '{payload.raw_command}'. "
                        f"Expected 'APPROVE <issue_id>' or 'REJECT <issue_id>'."
                    ),
                )

            action_verb, target_issue = parsed

            # If payload had an issue_id specified, ensure it matches target in command
            if payload.issue_id and payload.issue_id.upper() != target_issue.upper():
                return ApprovalValidationResult(
                    is_valid=False,
                    decision=ApprovalDecision.PENDING,
                    approval_id="UNKNOWN",
                    issue_id=payload.issue_id,
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=(
                        f"Approval command targeted '{target_issue}' but active request context "
                        f"is '{payload.issue_id}'. Issue mismatch rejected."
                    ),
                )

            # 2. Lookup approval request
            req = self._requests.get(target_issue)
            if not req:
                return ApprovalValidationResult(
                    is_valid=False,
                    decision=ApprovalDecision.PENDING,
                    approval_id="UNKNOWN",
                    issue_id=target_issue,
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=f"No approval request found for issue '{target_issue}'.",
                )

            # 3. Check for cancellation
            if req.status == ApprovalDecision.CANCELLED:
                return ApprovalValidationResult(
                    is_valid=False,
                    decision=ApprovalDecision.CANCELLED,
                    approval_id=req.approval_id,
                    issue_id=req.issue_id,
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=f"Issue '{req.issue_id}' was cancelled. Approval is not permitted.",
                )

            # 4. Check for duplicates (already decided)
            if req.status == ApprovalDecision.APPROVED:
                return ApprovalValidationResult(
                    is_valid=False,
                    decision=ApprovalDecision.APPROVED,
                    approval_id=req.approval_id,
                    issue_id=req.issue_id,
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=(
                        f"Duplicate approval: Issue '{req.issue_id}' was already approved by "
                        f"'{req.decided_by}' on {req.decided_at}. Re-execution blocked."
                    ),
                )

            if req.status == ApprovalDecision.REJECTED:
                return ApprovalValidationResult(
                    is_valid=False,
                    decision=ApprovalDecision.REJECTED,
                    approval_id=req.approval_id,
                    issue_id=req.issue_id,
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=(
                        f"Issue '{req.issue_id}' was previously rejected by '{req.decided_by}'. "
                        f"Proposal execution blocked."
                    ),
                )

            # 5. Check for expiration
            if req.is_expired() or req.status == ApprovalDecision.EXPIRED:
                req.status = ApprovalDecision.EXPIRED
                self._save_to_disk()
                return ApprovalValidationResult(
                    is_valid=False,
                    decision=ApprovalDecision.EXPIRED,
                    approval_id=req.approval_id,
                    issue_id=req.issue_id,
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=f"Approval request for issue '{req.issue_id}' expired at {req.expires_at}.",
                )

            # 6. Check user authorization
            if not self.is_user_authorized(payload.user_id):
                logger.warning(f"Unauthorized approval attempt by user '{payload.user_id}' for issue '{req.issue_id}'")
                return ApprovalValidationResult(
                    is_valid=False,
                    decision=req.status,
                    approval_id=req.approval_id,
                    issue_id=req.issue_id,
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=f"User '{payload.user_id}' is not in the approved developers allowlist.",
                )

            # 7. Apply Approved Decision
            now = datetime.now(timezone.utc)
            if action_verb == "APPROVE":
                token = f"EXEC-{req.issue_id}-{secrets.token_urlsafe(16)}"
                req.status = ApprovalDecision.APPROVED
                req.decided_by = payload.user_id
                req.decided_at = now
                self._active_tokens[req.issue_id] = token
                self._save_to_disk()

                logger.info(f"Issue {req.issue_id} APPROVED by {payload.user_id}. Generated token {token[:12]}...")
                return ApprovalValidationResult(
                    is_valid=True,
                    decision=ApprovalDecision.APPROVED,
                    approval_id=req.approval_id,
                    issue_id=req.issue_id,
                    decided_by=payload.user_id,
                    execution_permitted=True,
                    message=f"Approval granted by '{payload.user_id}'. Implementation permitted.",
                    execution_token=token,
                )

            # 8. Apply Rejected Decision
            elif action_verb == "REJECT":
                req.status = ApprovalDecision.REJECTED
                req.decided_by = payload.user_id
                req.decided_at = now
                req.rejection_reason = payload.rejection_reason or "Developer rejected proposed fix"
                self._save_to_disk()

                logger.info(f"Issue {req.issue_id} REJECTED by {payload.user_id}")
                return ApprovalValidationResult(
                    is_valid=True,
                    decision=ApprovalDecision.REJECTED,
                    approval_id=req.approval_id,
                    issue_id=req.issue_id,
                    decided_by=payload.user_id,
                    execution_permitted=False,
                    message=f"Proposal rejected by '{payload.user_id}'. Implementation cancelled.",
                )

            return ApprovalValidationResult(
                is_valid=False,
                decision=ApprovalDecision.PENDING,
                approval_id=req.approval_id,
                issue_id=req.issue_id,
                decided_by=payload.user_id,
                execution_permitted=False,
                message=f"Unrecognized action '{action_verb}'.",
            )

    # -----------------------------------------------------------------------
    # Code Modification Gate (Demonstrates modifications cannot start without approval)
    # -----------------------------------------------------------------------

    def authorize_code_modification(self, issue_id: str, execution_token: str) -> bool:
        """
        The critical execution boundary.
        Any attempt to modify repository files or create fix branches MUST pass through this gate.
        Enforces single-use tokens and confirmed approval state.
        """
        with self._lock:
            # Check token consumption
            if execution_token in self._consumed_tokens:
                raise WorkflowStateError(
                    message=f"Execution token has already been consumed. Duplicate execution blocked.",
                    current_state="TOKEN_EXHAUSTED",
                )

            # Check valid token
            expected_token = self._active_tokens.get(issue_id)
            if not expected_token or expected_token != execution_token:
                raise UnauthorizedApproverError(
                    user="UNKNOWN",
                    details={"error": "Invalid or missing execution token", "issue_id": issue_id},
                )

            # Check issue state
            req = self._requests.get(issue_id)
            if not req or req.status != ApprovalDecision.APPROVED:
                raise WorkflowStateError(
                    message=f"Cannot execute code modification: Issue '{issue_id}' is not in APPROVED state.",
                    current_state=req.status.value if req else "UNKNOWN",
                )

            # Consume token (single use)
            self._consumed_tokens.add(execution_token)
            del self._active_tokens[issue_id]
            logger.info(f"Execution token for issue {issue_id} verified and consumed. Modification gate OPEN.")
            return True

    # -----------------------------------------------------------------------
    # Parsing & Persistence Helpers
    # -----------------------------------------------------------------------

    def _parse_command(self, raw_text: str) -> Optional[Tuple[str, str]]:
        """Parses 'APPROVE <issue_id>' or 'REJECT <issue_id>' from chat message."""
        match = re.search(r"\b(APPROVE|REJECT)\s+([A-Za-z0-9_\-]+)\b", raw_text, re.IGNORECASE)
        if match:
            verb = match.group(1).upper()
            issue = match.group(2).upper()
            return verb, issue
        return None

    def _save_to_disk(self):
        """Atomically saves approval state to persistent storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "requests": {
                    k: v.model_dump(mode="json") for k, v in self._requests.items()
                },
            }
            temp_path = self.storage_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_path.replace(self.storage_path)
        except Exception as e:
            logger.error(f"Failed to persist approvals to {self.storage_path}: {e}")

    def _load_from_disk(self):
        """Loads approval state from disk if existing."""
        if not self.storage_path.exists():
            return
        try:
            raw = self.storage_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            for k, req_dict in data.get("requests", {}).items():
                self._requests[k] = ApprovalRequest.model_validate(req_dict)
            logger.info(f"Loaded {len(self._requests)} approval records from {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to load approval store from {self.storage_path}: {e}")


# Global singleton instance
approval_manager = ApprovalManager()

