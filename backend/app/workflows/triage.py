"""
Triage, Investigation, and Human Approval Workflow State Machine for DevFlow.

Manages the progression from message receipt through classification,
read-only code inspection, report generation, and the human approval gate.
"""

from enum import Enum
from typing import Dict, Optional

from app.core.exceptions import WorkflowStateError
from app.core.logging import get_logger
from app.models.approval import (
    ApprovalActionPayload,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalValidationResult,
)
from app.models.execution import ExecutionReport, ExecutionStatus, FixPlan
from app.models.investigation import InvestigationReport, InvestigationRequest
from app.models.reporting import EngineeringReport, GitHubReference
from app.services.approval_manager import ApprovalManager, approval_manager
from app.services.engineering_reporter import EngineeringReporter, engineering_reporter
from app.services.fix_executor import FixExecutor
from app.services.github_service import GitHubService, github_service
from app.services.investigation_engine import BugInvestigationEngine
from app.services.switch_reporter import SwitchReporter, switch_reporter

logger = get_logger("workflow.triage")


class TriageState(str, Enum):
    """Linear progression states for bug triage, investigation, approval, and execution."""

    IDLE = "IDLE"
    RECEIVED = "RECEIVED"
    CLASSIFYING = "CLASSIFYING"
    INSPECTING_REPO = "INSPECTING_REPO"
    REPRODUCING = "REPRODUCING"
    ANALYZING = "ANALYZING"
    REPORT_GENERATED = "REPORT_GENERATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    EXECUTION_COMPLETE = "EXECUTION_COMPLETE"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class TriageWorkflow:
    """Manages stateful triage, investigation, and controlled execution workflows keyed by session/room."""

    def __init__(
        self,
        engine: Optional[BugInvestigationEngine] = None,
        manager: Optional[ApprovalManager] = None,
        executor: Optional[FixExecutor] = None,
        reporter: Optional[EngineeringReporter] = None,
        switch: Optional[SwitchReporter] = None,
    ):
        self.engine = engine or BugInvestigationEngine()
        self.manager = manager or approval_manager
        self.executor = executor or FixExecutor(manager=self.manager)
        self.switch = switch or switch_reporter
        self.reporter = reporter or EngineeringReporter(switch=self.switch)
        self._states: Dict[str, TriageState] = {}
        self._reports: Dict[str, InvestigationReport] = {}
        self._approval_requests: Dict[str, ApprovalRequest] = {}
        self._execution_reports: Dict[str, ExecutionReport] = {}
        self._final_reports: Dict[str, EngineeringReport] = {}

    def get_state(self, session_id: str) -> TriageState:
        """Returns the current state for a given session."""
        return self._states.get(session_id, TriageState.IDLE)

    def run_investigation(
        self, session_id: str, request: InvestigationRequest
    ) -> InvestigationReport:
        """Executes the investigation workflow while updating state transitions."""
        current = self.get_state(session_id)
        if current not in (
            TriageState.IDLE,
            TriageState.REPORT_GENERATED,
            TriageState.REJECTED,
            TriageState.CANCELLED,
            TriageState.FAILED,
        ):
            raise WorkflowStateError(
                message=f"Cannot initiate investigation from active state '{current.value}'.",
                current_state=current.value,
            )

        try:
            self._states[session_id] = TriageState.RECEIVED
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.RECEIVED.value}")
            self.switch.report_bug_received(
                issue_id="PENDING",
                summary=request.description[:60],
                room_id=request.room_id,
            )

            self._states[session_id] = TriageState.CLASSIFYING
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.CLASSIFYING.value}")

            self._states[session_id] = TriageState.INSPECTING_REPO
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.INSPECTING_REPO.value}")
            self.switch.report_investigation_started(
                issue_id="PENDING",
                target_repo="demo_repository",
                room_id=request.room_id,
            )

            report = self.engine.investigate(request)

            self._states[session_id] = TriageState.REPORT_GENERATED
            self._reports[session_id] = report
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.REPORT_GENERATED.value}")
            self.switch.report_investigation_completed(report, room_id=request.room_id)
            return report

        except Exception as e:
            self._states[session_id] = TriageState.FAILED
            logger.error(f"[{session_id}] Investigation workflow failed: {e}")
            raise

    def publish_for_approval(
        self, session_id: str, report: Optional[InvestigationReport] = None
    ) -> ApprovalRequest:
        """
        Transitions investigation output to the human approval gate.
        Publishes diagnosis and proposed fix, generating a unique approval ID.
        """
        current = self.get_state(session_id)
        active_report = report or self._reports.get(session_id)

        if not active_report:
            raise WorkflowStateError(
                message="Cannot publish for approval without a completed investigation report.",
                current_state=current.value,
            )

        # Create approval request
        testing_plan = [
            f"Verify {active_report.bug_category.value} defect",
            "Regression tests against demo_repository",
            active_report.testing_strategy[:60],
        ]

        approval_req = self.manager.create_request(
            issue_id=active_report.issue_id,
            issue_title=active_report.issue_title,
            root_cause=active_report.root_cause,
            affected_files=active_report.affected_files,
            proposed_fix=active_report.proposed_solution,
            testing_plan=testing_plan,
        )

        self._states[session_id] = TriageState.AWAITING_APPROVAL
        self._approval_requests[session_id] = approval_req
        self.switch.report_approval_requested(approval_req)
        logger.info(
            f"[{session_id}] Published approval request {approval_req.approval_id} for issue {approval_req.issue_id}. "
            f"State -> {TriageState.AWAITING_APPROVAL.value}"
        )
        return approval_req

    def process_approval(
        self, session_id: str, payload: ApprovalActionPayload
    ) -> ApprovalValidationResult:
        """
        Validates developer approval or rejection action.
        Only transitions state to APPROVED if permission checks pass.
        """
        current = self.get_state(session_id)
        if current != TriageState.AWAITING_APPROVAL:
            raise WorkflowStateError(
                message=f"No active proposal awaiting approval in session '{session_id}'. Current state: {current.value}.",
                current_state=current.value,
            )

        result = self.manager.process_action(payload)
        self.switch.report_approval_decided(result)

        if result.is_valid and result.decision == ApprovalDecision.APPROVED:
            self._states[session_id] = TriageState.APPROVED
            logger.info(f"[{session_id}] State transitioned to {TriageState.APPROVED.value}")
        elif result.is_valid and result.decision == ApprovalDecision.REJECTED:
            self._states[session_id] = TriageState.REJECTED
            logger.info(f"[{session_id}] State transitioned to {TriageState.REJECTED.value}")

        return result

    def execute_fix(self, session_id: str, plan: FixPlan) -> ExecutionReport:
        """
        Executes an approved bug fix on an isolated branch and validates it with tests.
        State transitions: APPROVED -> IMPLEMENTING -> TESTING -> EXECUTION_COMPLETE.
        """
        current = self.get_state(session_id)
        if current != TriageState.APPROVED:
            raise WorkflowStateError(
                message=f"Cannot execute fix: Session '{session_id}' is in state '{current.value}', expected APPROVED.",
                current_state=current.value,
            )

        try:
            self._states[session_id] = TriageState.IMPLEMENTING
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.IMPLEMENTING.value}")
            target_files = [p.relative_path for p in plan.patches]
            self.switch.report_fix_started(
                issue_id=plan.issue_id,
                branch=f"devflow/fix-{plan.issue_id.lower()}",
                files=target_files,
            )

            self._states[session_id] = TriageState.TESTING
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.TESTING.value}")

            report = self.executor.execute_fix(plan)

            self._states[session_id] = TriageState.EXECUTION_COMPLETE
            self._execution_reports[session_id] = report
            self.switch.report_tests_completed(report)
            logger.info(
                f"[{session_id}] Workflow transitioned to {TriageState.EXECUTION_COMPLETE.value} "
                f"with status {report.execution_status.value}"
            )
            return report

        except Exception as e:
            self._states[session_id] = TriageState.FAILED
            logger.error(f"[{session_id}] Fix execution failed: {e}")
            raise

    def generate_final_report(
        self,
        session_id: str,
        github_ref: Optional[GitHubReference] = None,
        room_id: Optional[str] = None,
    ) -> EngineeringReport:
        """
        Builds and publishes the final Stage 8 engineering report combining all phases.
        """
        investigation = self._reports.get(session_id)
        approval = self._approval_requests.get(session_id)
        execution = self._execution_reports.get(session_id)

        if not investigation or not approval or not execution:
            raise WorkflowStateError(
                message=f"Cannot generate final report for session '{session_id}': requires investigation, approval, and execution.",
                current_state=self.get_state(session_id).value,
            )

        eng_report = self.reporter.build_engineering_report(
            investigation=investigation,
            approval=approval,
            execution=execution,
            github_ref=github_ref,
        )
        self.reporter.publish_workflow_conclusion(eng_report, room_id=room_id)
        self._final_reports[session_id] = eng_report
        return eng_report

    def get_final_report(self, session_id: str) -> Optional[EngineeringReport]:
        """Retrieves the final engineering report for a session."""
        return self._final_reports.get(session_id)

    def get_latest_report(self, session_id: str) -> Optional[InvestigationReport]:
        """Retrieves the latest generated report for a session."""
        return self._reports.get(session_id)

    def get_approval_request(self, session_id: str) -> Optional[ApprovalRequest]:
        """Retrieves the active approval request for a session."""
        return self._approval_requests.get(session_id)

    def get_execution_report(self, session_id: str) -> Optional[ExecutionReport]:
        """Retrieves the latest execution report for a session."""
        return self._execution_reports.get(session_id)
