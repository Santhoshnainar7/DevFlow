"""
Switch reporting service for DevFlow.

Formats and dispatches concise engineering updates across the 8 lifecycle stages:
1. Bug received
2. Investigation started
3. Investigation completed
4. Approval requested
5. Approval received or rejected
6. Fix implementation started
7. Tests completed
8. Final report published
"""

from typing import Dict, List, Optional
from app.core.logging import get_logger
from app.models.approval import ApprovalDecision, ApprovalRequest, ApprovalValidationResult
from app.models.execution import ExecutionReport, ExecutionStatus
from app.models.investigation import InvestigationReport
from app.models.reporting import EngineeringReport, StageUpdate, WorkflowStage

logger = get_logger("switch_reporter")


class SwitchReporter:
    """Manages concise, stage-appropriate communication for team chat rooms."""

    def __init__(self):
        self._history: Dict[str, List[StageUpdate]] = {}  # issue_id -> updates

    def get_updates(self, issue_id: str) -> List[StageUpdate]:
        """Retrieves all chronological stage updates for an issue."""
        return self._history.get(issue_id, [])

    def record_update(self, update: StageUpdate) -> StageUpdate:
        """Stores a stage update in the issue's communication history."""
        if update.issue_id not in self._history:
            self._history[update.issue_id] = []
        self._history[update.issue_id].append(update)
        logger.info(f"[{update.issue_id}] Stage [{update.stage.value}]: {update.message[:80]}...")
        return update

    # -----------------------------------------------------------------------
    # Stage Message Formatters
    # -----------------------------------------------------------------------

    def report_bug_received(self, issue_id: str, summary: str, room_id: Optional[str] = None) -> StageUpdate:
        """Stage 1: Acknowledge bug receipt."""
        msg = f"Bug report received [{issue_id}]: {summary}. Initial triage queued."
        update = StageUpdate(
            stage=WorkflowStage.BUG_RECEIVED,
            issue_id=issue_id,
            message=msg,
            room_id=room_id,
        )
        return self.record_update(update)

    def report_investigation_started(self, issue_id: str, target_repo: str, room_id: Optional[str] = None) -> StageUpdate:
        """Stage 2: Notify that read-only investigation is in progress."""
        msg = f"Investigating [{issue_id}]: Inspecting source files and test suites in {target_repo}..."
        update = StageUpdate(
            stage=WorkflowStage.INVESTIGATION_STARTED,
            issue_id=issue_id,
            message=msg,
            room_id=room_id,
        )
        return self.record_update(update)

    def report_investigation_completed(self, report: InvestigationReport, room_id: Optional[str] = None) -> StageUpdate:
        """Stage 3: Publish full structured diagnosis."""
        msg = f"Investigation completed for [{report.issue_id}]. Category: {report.bug_category.value} | Severity: {report.severity.value}.\n\n{report.to_formatted_report()}"
        update = StageUpdate(
            stage=WorkflowStage.INVESTIGATION_COMPLETED,
            issue_id=report.issue_id,
            message=msg,
            room_id=room_id,
            metadata={"category": report.bug_category.value, "severity": report.severity.value},
        )
        return self.record_update(update)

    def report_approval_requested(self, approval_req: ApprovalRequest, room_id: Optional[str] = None) -> StageUpdate:
        """Stage 4: Post the human approval request prompt."""
        msg = approval_req.to_switch_prompt()
        update = StageUpdate(
            stage=WorkflowStage.APPROVAL_REQUESTED,
            issue_id=approval_req.issue_id,
            message=msg,
            room_id=room_id,
            metadata={"approval_id": approval_req.approval_id, "expires_at": approval_req.expires_at.isoformat()},
        )
        return self.record_update(update)

    def report_approval_decided(self, validation: ApprovalValidationResult, room_id: Optional[str] = None) -> StageUpdate:
        """Stage 5: Announce approval decision."""
        if validation.decision == ApprovalDecision.APPROVED:
            msg = f"Fix APPROVED for [{validation.issue_id}] by @{validation.decided_by}. Execution gate opened."
        elif validation.decision == ApprovalDecision.REJECTED:
            msg = f"Fix REJECTED for [{validation.issue_id}] by @{validation.decided_by}. Implementation cancelled."
        else:
            msg = f"Approval action rejected for [{validation.issue_id}]: {validation.message}"

        update = StageUpdate(
            stage=WorkflowStage.APPROVAL_DECIDED,
            issue_id=validation.issue_id,
            message=msg,
            room_id=room_id,
            metadata={"decision": validation.decision.value, "decided_by": validation.decided_by},
        )
        return self.record_update(update)

    def report_fix_started(self, issue_id: str, branch: str, files: List[str], room_id: Optional[str] = None) -> StageUpdate:
        """Stage 6: Notify branch checkout and fix application."""
        file_list = ", ".join(files) if files else "target files"
        msg = f"Fix implementation started for [{issue_id}] on isolated branch `{branch}`. Modifying {file_list}."
        update = StageUpdate(
            stage=WorkflowStage.FIX_IMPLEMENTATION_STARTED,
            issue_id=issue_id,
            message=msg,
            room_id=room_id,
            metadata={"branch": branch, "files": files},
        )
        return self.record_update(update)

    def report_tests_completed(self, exec_report: ExecutionReport, room_id: Optional[str] = None) -> StageUpdate:
        """Stage 7: Announce test execution outcome."""
        if exec_report.execution_status == ExecutionStatus.SUCCESS:
            msg = f"Tests COMPLETED for [{exec_report.issue_id}]: {exec_report.tests_passed}/{exec_report.tests_executed} passed on branch `{exec_report.branch}`."
        else:
            msg = f"Tests FAILED for [{exec_report.issue_id}]: {exec_report.tests_failed} failed ({exec_report.execution_status.value}). Reverting code changes."

        update = StageUpdate(
            stage=WorkflowStage.TESTS_COMPLETED,
            issue_id=exec_report.issue_id,
            message=msg,
            room_id=room_id,
            metadata={"status": exec_report.execution_status.value, "passed": exec_report.tests_passed, "failed": exec_report.tests_failed},
        )
        return self.record_update(update)

    def report_final_summary(self, eng_report: EngineeringReport, room_id: Optional[str] = None) -> StageUpdate:
        """Stage 8: Publish final comprehensive engineering report."""
        msg = f"Final Engineering Report [{eng_report.issue_id}]:\n\n{eng_report.to_formatted_report()}"
        update = StageUpdate(
            stage=WorkflowStage.FINAL_REPORT_PUBLISHED,
            issue_id=eng_report.issue_id,
            message=msg,
            room_id=room_id,
            metadata={"status": eng_report.execution_status},
        )
        return self.record_update(update)


# Global singleton reporter instance
switch_reporter = SwitchReporter()

