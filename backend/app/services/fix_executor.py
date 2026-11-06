"""
Fix Executor Orchestrator for DevFlow Phase 05.

Implements the 10-step controlled code fixing and test execution workflow:
1. Receive approved issue
2. Validate approval again
3. Verify repository state
4. Create isolated working branch
5. Apply proposed fix
6. Inspect resulting diff
7. Run relevant tests
8. Run broader test suite
9. Analyze failures
10. Prepare standardized execution report
"""

from pathlib import Path
from typing import List, Optional

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedApproverError, WorkflowStateError
from app.core.logging import get_logger
from app.models.execution import (
    ExecutionReport,
    ExecutionStatus,
    FixPatch,
    FixPlan,
)
from app.services.approval_manager import ApprovalManager, approval_manager
from app.services.controlled_test_runner import ControlledTestRunner
from app.services.git_workflow import GitWorkflow

logger = get_logger("fix_executor")


class FixExecutor:
    """Executes validated code fixes on isolated branches and evaluates automated test outcomes."""

    def __init__(
        self,
        repo_path: Optional[Path] = None,
        manager: Optional[ApprovalManager] = None,
        test_timeout_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.repo_path = Path(repo_path or settings.DEVFLOW_REPO_PATH).resolve()
        self.manager = manager or approval_manager
        self.test_timeout_seconds = (
            test_timeout_seconds
            if test_timeout_seconds is not None
            else settings.DEVFLOW_TEST_TIMEOUT_SECONDS
        )

    def execute_fix(self, plan: FixPlan) -> ExecutionReport:
        """
        Executes the full 10-step controlled fix workflow.
        Strictly enforces that unapproved or unauthorized modifications cannot execute.
        """
        logger.info(f"Starting controlled fix execution for issue '{plan.issue_id}' (Approval ID: {plan.approval_id})")

        # -------------------------------------------------------------------
        # Step 2: Validate approval again (Server-Side Authorization Check)
        # -------------------------------------------------------------------
        try:
            self.manager.authorize_code_modification(plan.issue_id, plan.execution_token)
        except (UnauthorizedApproverError, WorkflowStateError) as e:
            logger.error(f"Approval validation failed for issue '{plan.issue_id}': {e.message}")
            return ExecutionReport(
                issue_id=plan.issue_id,
                approval_id=plan.approval_id,
                branch="none",
                files_changed=[],
                changes_made="None. Approval validation failed.",
                tests_executed=0,
                tests_passed=0,
                tests_failed=0,
                execution_status=ExecutionStatus.FAILED_INVALID_APPROVAL,
                remaining_risks="Execution blocked by security gatekeeper.",
                error_details=f"Authorization failure: {e.message}",
                requires_human_intervention=True,
            )

        git_wf = GitWorkflow(repo_path=self.repo_path)

        # -------------------------------------------------------------------
        # Step 3: Verify repository state (Check for uncommitted changes)
        # -------------------------------------------------------------------
        has_dirty, dirty_msg = git_wf.check_uncommitted_changes()
        if has_dirty:
            logger.error(f"Repository is dirty; refusing to overwrite developer changes: {dirty_msg}")
            return ExecutionReport(
                issue_id=plan.issue_id,
                approval_id=plan.approval_id,
                branch="none",
                files_changed=[],
                changes_made="None. Aborted to preserve existing developer changes.",
                tests_executed=0,
                tests_passed=0,
                tests_failed=0,
                execution_status=ExecutionStatus.FAILED_DIRTY_REPO,
                remaining_risks="Developer working tree must be committed or stashed before fix execution.",
                error_details=dirty_msg,
                requires_human_intervention=True,
            )

        # -------------------------------------------------------------------
        # Step 4: Create isolated working branch
        # -------------------------------------------------------------------
        branch_name = git_wf.create_isolated_branch(plan.issue_id)

        # -------------------------------------------------------------------
        # Step 5: Apply proposed fix (Restricted to authorized workspace)
        # -------------------------------------------------------------------
        files_changed: List[str] = []
        for patch in plan.patches:
            success, rel_or_err = git_wf.apply_patch(patch.relative_path, patch.new_content)
            if not success:
                logger.error(f"Patch rejected for '{patch.relative_path}': {rel_or_err}")
                git_wf.revert_workflow_changes()
                return ExecutionReport(
                    issue_id=plan.issue_id,
                    approval_id=plan.approval_id,
                    branch=branch_name,
                    files_changed=[],
                    changes_made="None. Patch application was rejected.",
                    tests_executed=0,
                    tests_passed=0,
                    tests_failed=0,
                    execution_status=ExecutionStatus.FAILED_UNAUTHORIZED_FILE,
                    remaining_risks="Attempted modification outside authorized workspace or invalid file extension.",
                    error_details=rel_or_err,
                    requires_human_intervention=True,
                )
            files_changed.append(rel_or_err)

        # -------------------------------------------------------------------
        # Step 6: Inspect resulting diff
        # -------------------------------------------------------------------
        diff_text = git_wf.compute_diff()
        changes_summary = plan.summary_of_changes or f"Applied {len(files_changed)} targeted code patches."

        # -------------------------------------------------------------------
        # Step 7 & 8: Run relevant and broader tests
        # -------------------------------------------------------------------
        test_runner = ControlledTestRunner(
            repo_path=self.repo_path,
            timeout_seconds=plan.timeout_seconds or self.test_timeout_seconds,
        )

        test_result = test_runner.run_tests(target_tests=plan.target_tests)

        # -------------------------------------------------------------------
        # Step 9: Analyze failures and handle revert
        # -------------------------------------------------------------------
        if test_result.is_timeout:
            git_wf.revert_workflow_changes()
            return ExecutionReport(
                issue_id=plan.issue_id,
                approval_id=plan.approval_id,
                branch=branch_name,
                files_changed=files_changed,
                changes_made=changes_summary,
                tests_executed=test_result.tests_executed,
                tests_passed=test_result.tests_passed,
                tests_failed=test_result.tests_failed,
                execution_status=ExecutionStatus.FAILED_TIMEOUT,
                remaining_risks="Automated test suite exceeded time budget. Reverted code modifications.",
                diff=diff_text,
                test_output=test_result.stdout,
                error_details=test_result.failure_explanation,
                requires_human_intervention=True,
            )

        if test_result.is_dependency_missing:
            git_wf.revert_workflow_changes()
            return ExecutionReport(
                issue_id=plan.issue_id,
                approval_id=plan.approval_id,
                branch=branch_name,
                files_changed=files_changed,
                changes_made=changes_summary,
                tests_executed=test_result.tests_executed,
                tests_passed=test_result.tests_passed,
                tests_failed=test_result.tests_failed,
                execution_status=ExecutionStatus.FAILED_DEPENDENCY,
                remaining_risks="Missing package or broken imports in test environment. Reverted changes.",
                diff=diff_text,
                test_output=test_result.stdout,
                error_details=test_result.failure_explanation,
                requires_human_intervention=True,
            )

        if not test_result.passed or test_result.tests_failed > 0:
            # Revert workflow changes on failure to restore green baseline
            git_wf.revert_workflow_changes()
            return ExecutionReport(
                issue_id=plan.issue_id,
                approval_id=plan.approval_id,
                branch=branch_name,
                files_changed=files_changed,
                changes_made=changes_summary,
                tests_executed=test_result.tests_executed,
                tests_passed=test_result.tests_passed,
                tests_failed=test_result.tests_failed,
                execution_status=ExecutionStatus.FAILED_TESTS,
                remaining_risks="Proposed patch did not satisfy all test assertions. Changes safely reverted.",
                diff=diff_text,
                test_output=test_result.stdout,
                error_details=test_result.failure_explanation,
                requires_human_intervention=True,
            )

        # -------------------------------------------------------------------
        # Step 10: Prepare execution report (Success!)
        # -------------------------------------------------------------------
        logger.info(f"Fix for issue '{plan.issue_id}' succeeded: {test_result.tests_passed} tests passed!")
        return ExecutionReport(
            issue_id=plan.issue_id,
            approval_id=plan.approval_id,
            branch=branch_name,
            files_changed=files_changed,
            changes_made=changes_summary,
            tests_executed=test_result.tests_executed,
            tests_passed=test_result.tests_passed,
            tests_failed=test_result.tests_failed,
            execution_status=ExecutionStatus.SUCCESS,
            remaining_risks="Fix staged on isolated branch. Ready for code review and manual merge.",
            diff=diff_text,
            test_output=test_result.stdout,
            requires_human_intervention=False,
        )

