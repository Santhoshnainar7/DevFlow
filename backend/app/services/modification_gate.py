"""
Code Modification Gate for DevFlow.

Serves as the security gatekeeper for any filesystem or Git write operations.
Demonstrates that no code modifications or fix branches can be initiated
without a verified, single-use approval execution token.
"""

from pathlib import Path
from typing import Dict, List, Optional

from app.core.exceptions import UnauthorizedApproverError, WorkflowStateError
from app.core.logging import get_logger
from app.services.approval_manager import ApprovalManager, approval_manager

logger = get_logger("modification_gate")


class CodeModificationGate:
    """Guards repository write operations behind verified human approvals."""

    def __init__(self, manager: Optional[ApprovalManager] = None):
        self.manager = manager or approval_manager

    def request_write_access(self, issue_id: str, execution_token: Optional[str]) -> bool:
        """
        Validates authorization before any write or branch operation begins.
        Raises UnauthorizedApproverError if execution_token is missing or invalid.
        Raises WorkflowStateError if duplicate or unapproved.
        """
        if not execution_token:
            logger.error(f"Write operation blocked for issue '{issue_id}': No execution token provided.")
            raise UnauthorizedApproverError(
                user="ANONYMOUS",
                details={
                    "error": "Missing approval execution token",
                    "issue_id": issue_id,
                    "action": "CODE_MODIFICATION_BLOCKED",
                },
            )

        # Enforces server-side token validation and single-use consumption
        self.manager.authorize_code_modification(issue_id, execution_token)
        logger.info(f"Write access granted for issue '{issue_id}'. Code modification authorized.")
        return True

    def apply_patch(
        self,
        issue_id: str,
        execution_token: Optional[str],
        target_file: str,
        patch_content: str,
    ) -> bool:
        """
        Example guarded write method.
        Will NOT execute if request_write_access fails.
        """
        self.request_write_access(issue_id, execution_token)

        # Once verified, write would be executed (deferred to Phase 05)
        logger.info(f"Simulating patch application for {target_file} on approved issue {issue_id}")
        return True


# Global singleton gate instance
modification_gate = CodeModificationGate()

