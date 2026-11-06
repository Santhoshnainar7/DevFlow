"""
Comprehensive engineering reporting orchestrator for DevFlow Phase 06.

Combines diagnostic findings, human approval audits, code diffs,
test results, and GitHub references into standardized engineering reports.
"""

from typing import List, Optional

from app.core.logging import get_logger
from app.models.approval import ApprovalRequest
from app.models.execution import ExecutionReport, ExecutionStatus
from app.models.investigation import InvestigationReport
from app.models.reporting import EngineeringReport, GitHubReference
from app.services.github_service import GitHubService, github_service
from app.services.switch_reporter import SwitchReporter, switch_reporter

logger = get_logger("engineering_reporter")


class EngineeringReporter:
    """Generates and publishes end-to-end engineering reports across Switch and GitHub."""

    def __init__(
        self,
        switch: Optional[SwitchReporter] = None,
        github: Optional[GitHubService] = None,
    ):
        self.switch = switch or switch_reporter
        self.github = github or github_service

    def build_engineering_report(
        self,
        investigation: InvestigationReport,
        approval: ApprovalRequest,
        execution: ExecutionReport,
        github_ref: Optional[GitHubReference] = None,
    ) -> EngineeringReport:
        """
        Synthesizes the complete final engineering report following Part C specification.
        """
        implemented_sol = (
            execution.changes_made
            if execution.execution_status == ExecutionStatus.SUCCESS
            else f"Execution did not succeed ({execution.execution_status.value}). Fix was not applied."
        )

        eng_report = EngineeringReport(
            issue_id=investigation.issue_id,
            approval_id=approval.approval_id,
            description=investigation.description,
            root_cause=investigation.root_cause,
            proposed_solution=investigation.proposed_solution,
            implemented_solution=implemented_sol,
            files_changed=execution.files_changed,
            branch=execution.branch,
            tests_executed=execution.tests_executed,
            tests_passed=execution.tests_passed,
            tests_failed=execution.tests_failed,
            execution_status=execution.execution_status.value,
            remaining_risks=execution.remaining_risks,
            github=github_ref,
            diff=execution.diff,
        )

        return eng_report

    def publish_workflow_conclusion(
        self,
        eng_report: EngineeringReport,
        room_id: Optional[str] = None,
    ) -> EngineeringReport:
        """
        Dispatches Stage 8 notification to Switch and logs conclusion.
        """
        self.switch.report_final_summary(eng_report, room_id=room_id)
        logger.info(f"Published final engineering report for issue '{eng_report.issue_id}'")
        return eng_report


# Global singleton engineering reporter instance
engineering_reporter = EngineeringReporter()

