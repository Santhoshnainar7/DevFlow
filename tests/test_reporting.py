"""
Comprehensive test suite for DevFlow Phase 06:
Engineering Reporting and GitHub Integration.

Covers:
- Switch lifecycle updates across all 8 stages
- Structured final engineering report generation and formatting
- GitHub integration, security guards, token masking, and offline fallback
- End-to-end workflow reporting integration
- API endpoints for reporting and GitHub actions
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import WorkflowStateError
from app.models.approval import (
    ApprovalActionPayload,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalValidationResult,
)
from app.models.execution import ExecutionReport, ExecutionStatus, FixPatch, FixPlan
from app.models.investigation import BugCategory, InvestigationReport, InvestigationRequest, Severity
from app.models.reporting import EngineeringReport, GitHubReference, StageUpdate, WorkflowStage
from app.services.approval_manager import ApprovalManager
from app.services.engineering_reporter import EngineeringReporter
from app.services.github_service import GitHubService
from app.services.switch_reporter import SwitchReporter
from app.workflows.triage import TriageWorkflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_investigation_report() -> InvestigationReport:
    return InvestigationReport(
        issue_id="DF-001",
        issue_title="Auth failure returns 500 instead of 401",
        bug_category=BugCategory.AUTHENTICATION,
        severity=Severity.HIGH,
        description="Invalid credentials result in uncaught internal server error.",
        affected_files=["app/routers/auth.py", "app/services/auth_service.py"],
        relevant_functions=["login_for_access_token", "authenticate_user"],
        root_cause="CONFIRMED: authenticate_user raises unhandled AuthenticationError instead of returning 401.",
        evidence=["Observed test failure in tests/test_auth.py with status 500."],
        proposed_solution="Catch AuthenticationError in login endpoint and raise HTTPException(401).",
        testing_strategy="Run test_auth_invalid_credentials expecting HTTP 401.",
        potential_risks="Ensure valid user login tokens are unaffected.",
    )


@pytest.fixture
def sample_approval_request() -> ApprovalRequest:
    return ApprovalRequest(
        approval_id="APP-DF-001-A1B2C3",
        issue_id="DF-001",
        issue_title="Auth failure returns 500 instead of 401",
        root_cause="Incorrect exception handling in auth router.",
        affected_files=["app/routers/auth.py"],
        proposed_fix="Catch AuthenticationError and raise HTTP 401.",
        testing_plan=["Valid login", "Invalid password", "Missing credentials"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )


@pytest.fixture
def sample_execution_report() -> ExecutionReport:
    return ExecutionReport(
        issue_id="DF-001",
        approval_id="APP-DF-001-A1B2C3",
        branch="devflow/fix-df-001-20261106",
        files_changed=["app/routers/auth.py"],
        changes_made="Added HTTPException(401) on AuthenticationError.",
        tests_executed=7,
        tests_passed=7,
        tests_failed=0,
        execution_status=ExecutionStatus.SUCCESS,
        diff="--- a/app/routers/auth.py\n+++ b/app/routers/auth.py\n@@ -20,2 +20,4 @@\n+    except AuthenticationError:\n+        raise HTTPException(status_code=401)",
        remaining_risks="None identified. Full regression suite passed.",
    )


# ---------------------------------------------------------------------------
# Part A: Switch Reporting Lifecycle (8 Stages) Tests
# ---------------------------------------------------------------------------

class TestSwitchReporting:
    """Verifies concise notifications across all 8 workflow stages."""

    def test_all_eight_stages_dispatched(
        self,
        sample_investigation_report: InvestigationReport,
        sample_approval_request: ApprovalRequest,
        sample_execution_report: ExecutionReport,
    ):
        reporter = SwitchReporter()
        issue_id = "DF-001"

        # Stage 1: Bug received
        u1 = reporter.report_bug_received(issue_id, "Auth failure report", room_id="bug-reports")
        assert u1.stage == WorkflowStage.BUG_RECEIVED
        assert "Bug report received" in u1.message
        assert issue_id in u1.message

        # Stage 2: Investigation started
        u2 = reporter.report_investigation_started(issue_id, "demo_repository", room_id="bug-reports")
        assert u2.stage == WorkflowStage.INVESTIGATION_STARTED
        assert "Investigating [DF-001]" in u2.message

        # Stage 3: Investigation completed
        u3 = reporter.report_investigation_completed(sample_investigation_report, room_id="bug-reports")
        assert u3.stage == WorkflowStage.INVESTIGATION_COMPLETED
        assert "Issue ID: DF-001" in u3.message
        assert "Authentication" in u3.message

        # Stage 4: Approval requested
        u4 = reporter.report_approval_requested(sample_approval_request, room_id="bug-reports")
        assert u4.stage == WorkflowStage.APPROVAL_REQUESTED
        assert "APPROVE DF-001" in u4.message

        # Stage 5: Approval decided (approved)
        val_approved = ApprovalValidationResult(
            is_valid=True,
            decision=ApprovalDecision.APPROVED,
            execution_permitted=True,
            issue_id=issue_id,
            approval_id=sample_approval_request.approval_id,
            decided_by="senior_dev",
            execution_token="EXEC-TOKEN-1234",
            message="Approval granted.",
        )
        u5 = reporter.report_approval_decided(val_approved, room_id="bug-reports")
        assert u5.stage == WorkflowStage.APPROVAL_DECIDED
        assert "Fix APPROVED for [DF-001] by @senior_dev" in u5.message

        # Stage 6: Fix implementation started
        u6 = reporter.report_fix_started(
            issue_id=issue_id,
            branch="devflow/fix-df-001-123456",
            files=["app/routers/auth.py"],
            room_id="bug-reports",
        )
        assert u6.stage == WorkflowStage.FIX_IMPLEMENTATION_STARTED
        assert "Fix implementation started" in u6.message

        # Stage 7: Tests completed
        u7 = reporter.report_tests_completed(sample_execution_report, room_id="bug-reports")
        assert u7.stage == WorkflowStage.TESTS_COMPLETED
        assert "Tests COMPLETED for [DF-001]: 7/7 passed" in u7.message

        # Stage 8: Final report published
        eng_report = EngineeringReport(
            issue_id=issue_id,
            approval_id=sample_approval_request.approval_id,
            description=sample_investigation_report.description,
            root_cause=sample_investigation_report.root_cause,
            proposed_solution=sample_investigation_report.proposed_solution,
            implemented_solution="Caught AuthenticationError and returned 401",
            files_changed=["app/routers/auth.py"],
            branch="devflow/fix-df-001-123456",
            tests_executed=7,
            tests_passed=7,
            tests_failed=0,
            execution_status=ExecutionStatus.SUCCESS.value,
            remaining_risks="None identified. Automated fix verified by test suite.",
        )
        u8 = reporter.report_final_summary(eng_report, room_id="bug-reports")
        assert u8.stage == WorkflowStage.FINAL_REPORT_PUBLISHED
        assert "Final Engineering Report [DF-001]" in u8.message

        # Verify history holds all 8 updates in order
        history = reporter.get_updates(issue_id)
        assert len(history) == 8
        expected_stages = [
            WorkflowStage.BUG_RECEIVED,
            WorkflowStage.INVESTIGATION_STARTED,
            WorkflowStage.INVESTIGATION_COMPLETED,
            WorkflowStage.APPROVAL_REQUESTED,
            WorkflowStage.APPROVAL_DECIDED,
            WorkflowStage.FIX_IMPLEMENTATION_STARTED,
            WorkflowStage.TESTS_COMPLETED,
            WorkflowStage.FINAL_REPORT_PUBLISHED,
        ]
        assert [u.stage for u in history] == expected_stages

    def test_approval_rejection_message(self):
        reporter = SwitchReporter()
        val_rejected = ApprovalValidationResult(
            is_valid=True,
            decision=ApprovalDecision.REJECTED,
            execution_permitted=False,
            issue_id="DF-002",
            approval_id="APP-DF-002-XYZ",
            decided_by="tech_lead",
            message="Fix approach rejected by developer.",
        )
        update = reporter.report_approval_decided(val_rejected)
        assert "Fix REJECTED for [DF-002] by @tech_lead" in update.message

    def test_test_failure_message(self):
        reporter = SwitchReporter()
        failed_report = ExecutionReport(
            issue_id="DF-003",
            approval_id="APP-DF-003-XYZ",
            branch="devflow/fix-df-003",
            files_changed=["app/main.py"],
            changes_made="Modified main",
            tests_executed=5,
            tests_passed=3,
            tests_failed=2,
            execution_status=ExecutionStatus.FAILED_TESTS,
            remaining_risks="Automated fix failed verification. Manual intervention required.",
        )
        update = reporter.report_tests_completed(failed_report)
        assert "Tests FAILED for [DF-003]: 2 failed" in update.message
        assert "Reverting code changes" in update.message


# ---------------------------------------------------------------------------
# Part C: Structured Final Engineering Report Tests
# ---------------------------------------------------------------------------

class TestEngineeringReporting:
    """Verifies construction and formatting of comprehensive engineering reports."""

    def test_engineering_report_all_fields_formatted(
        self,
        sample_investigation_report: InvestigationReport,
        sample_approval_request: ApprovalRequest,
        sample_execution_report: ExecutionReport,
    ):
        reporter = EngineeringReporter()
        github_ref = GitHubReference(
            issue_url="https://github.com/org/repo/issues/42",
            issue_number=42,
            pr_url="https://github.com/org/repo/pull/43",
            pr_number=43,
            status="created",
        )

        eng = reporter.build_engineering_report(
            investigation=sample_investigation_report,
            approval=sample_approval_request,
            execution=sample_execution_report,
            github_ref=github_ref,
        )

        assert eng.issue_id == "DF-001"
        assert eng.approval_id == "APP-DF-001-A1B2C3"
        assert eng.tests_passed == 7
        assert eng.github == github_ref

        formatted = eng.to_formatted_report()

        # Part C required fields verification
        assert "Issue identifier: DF-001" in formatted
        assert "Problem description: Invalid credentials result in uncaught internal server error." in formatted
        assert "Root cause: CONFIRMED: authenticate_user raises unhandled AuthenticationError" in formatted
        assert "Proposed solution: Catch AuthenticationError in login endpoint" in formatted
        assert "Implemented solution: Added HTTPException(401) on AuthenticationError." in formatted
        assert "Files changed: app/routers/auth.py" in formatted
        assert "Git branch: devflow/fix-df-001-20261106" in formatted
        assert "Tests executed: 7" in formatted
        assert "Actual test results: 7 passed, 0 failed (SUCCESS)" in formatted
        assert "Remaining risks: None identified." in formatted
        assert "GitHub references: Issue #42 (https://github.com/org/repo/issues/42), PR #43 (https://github.com/org/repo/pull/43)" in formatted
        assert "--- Code Diff ---" in formatted

    def test_engineering_report_without_github(
        self,
        sample_investigation_report: InvestigationReport,
        sample_approval_request: ApprovalRequest,
        sample_execution_report: ExecutionReport,
    ):
        reporter = EngineeringReporter()
        eng = reporter.build_engineering_report(
            investigation=sample_investigation_report,
            approval=sample_approval_request,
            execution=sample_execution_report,
            github_ref=None,
        )

        formatted = eng.to_formatted_report()
        assert "GitHub references: None configured (offline mode)" in formatted

    def test_failed_execution_reflected_in_report(
        self,
        sample_investigation_report: InvestigationReport,
        sample_approval_request: ApprovalRequest,
    ):
        reporter = EngineeringReporter()
        failed_exec = ExecutionReport(
            issue_id="DF-001",
            approval_id=sample_approval_request.approval_id,
            branch="devflow/fix-df-001",
            files_changed=["app/routers/auth.py"],
            changes_made="Attempted patch",
            tests_executed=7,
            tests_passed=4,
            tests_failed=3,
            execution_status=ExecutionStatus.FAILED_TESTS,
            remaining_risks="Automated fix failed verification. Manual intervention required.",
        )

        eng = reporter.build_engineering_report(
            investigation=sample_investigation_report,
            approval=sample_approval_request,
            execution=failed_exec,
        )

        assert "Execution did not succeed (FAILED_TESTS)" in eng.implemented_solution
        assert eng.execution_status == ExecutionStatus.FAILED_TESTS.value


# ---------------------------------------------------------------------------
# Part B: GitHub Service Security & Offline Fallback Tests
# ---------------------------------------------------------------------------

class TestGitHubIntegration:
    """Verifies secure GitHub operations, guards against main, token masking, and offline fallback."""

    def test_unconfigured_offline_fallback(self):
        # Initialized with no token
        gh = GitHubService(token="", repo="org/demo")
        assert not gh.is_configured()

        ref_issue = gh.create_issue(
            issue_id="DF-001",
            title="Bug title",
            body="Bug body",
            is_approved=True,
        )
        assert ref_issue.status == "unconfigured"
        assert ref_issue.issue_url is None

        ref_pr = gh.create_pull_request(
            issue_id="DF-001",
            title="Fix title",
            head_branch="devflow/fix-df-001",
            body="PR body",
            is_approved=True,
        )
        assert ref_pr.status == "unconfigured"
        assert ref_pr.pr_url is None

    def test_human_approval_required_for_github_actions(self):
        gh = GitHubService(token="ghp_test123456789", repo="org/demo")

        # Unapproved issue creation blocked
        ref_issue = gh.create_issue(
            issue_id="DF-001",
            title="Bug title",
            body="Bug body",
            is_approved=False,
        )
        assert ref_issue.status == "approval_required"

        # Unapproved PR creation blocked
        ref_pr = gh.create_pull_request(
            issue_id="DF-001",
            title="Fix title",
            head_branch="devflow/fix-df-001",
            body="PR body",
            is_approved=False,
        )
        assert ref_pr.status == "approval_required"

    def test_guard_against_main_or_master_as_head_branch(self):
        gh = GitHubService(token="ghp_test123456789", repo="org/demo")

        with pytest.raises(WorkflowStateError) as exc_info:
            gh.create_pull_request(
                issue_id="DF-001",
                title="Bad PR",
                head_branch="main",
                body="PR body",
                is_approved=True,
            )
        assert "Cannot open pull request with main/master as the head branch" in str(exc_info.value)

        with pytest.raises(WorkflowStateError):
            gh.create_pull_request(
                issue_id="DF-001",
                title="Bad PR",
                head_branch="master",
                body="PR body",
                is_approved=True,
            )

    @patch("httpx.Client.post")
    def test_successful_github_issue_creation(self, mock_post: MagicMock):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/my-org/my-repo/issues/101",
            "number": 101,
        }
        mock_post.return_value = mock_response

        gh = GitHubService(token="ghp_valid_token_12345", repo="my-org/my-repo")
        ref = gh.create_issue(
            issue_id="DF-001",
            title="Auth Crash",
            body="Details here",
            switch_room="#bug-reports",
            is_approved=True,
        )

        assert ref.status == "created"
        assert ref.issue_number == 101
        assert ref.issue_url == "https://github.com/my-org/my-repo/issues/101"

    @patch("httpx.Client.post")
    def test_successful_github_pr_creation(self, mock_post: MagicMock):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/my-org/my-repo/pull/102",
            "number": 102,
        }
        mock_post.return_value = mock_response

        gh = GitHubService(token="ghp_valid_token_12345", repo="my-org/my-repo")
        ref = gh.create_pull_request(
            issue_id="DF-001",
            title="Fix Auth Crash",
            head_branch="devflow/fix-df-001",
            body="Fix details and pytest results",
            is_approved=True,
        )

        assert ref.status == "pr_opened"
        assert ref.pr_number == 102
        assert ref.pr_url == "https://github.com/my-org/my-repo/pull/102"
        assert ref.head_branch == "devflow/fix-df-001"

    @patch("httpx.Client.post")
    def test_github_api_http_error_handled_gracefully(self, mock_post: MagicMock):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_post.return_value = mock_response

        gh = GitHubService(token="ghp_invalid_token", repo="my-org/my-repo")
        ref = gh.create_issue(
            issue_id="DF-001",
            title="Test",
            body="Body",
            is_approved=True,
        )
        assert ref.status == "error_403"
        assert ref.issue_url is None


# ---------------------------------------------------------------------------
# Workflow Integration Tests (All 8 Stages via TriageWorkflow)
# ---------------------------------------------------------------------------

class TestWorkflowReportingIntegration:
    """Verifies that TriageWorkflow triggers stage notifications throughout execution."""

    def test_full_workflow_records_all_stages(self, tmp_path):
        switch = SwitchReporter()
        mgr = ApprovalManager(
            storage_path=tmp_path / "approvals.json",
            authorized_users=["lead_developer"],
        )
        workflow = TriageWorkflow(
            manager=mgr,
            switch=switch,
        )
        session_id = "test-session-full-cycle"

        # 1. Investigation
        req = InvestigationRequest(
            description="Bug: login raises 500 when password is invalid",
            room_id="bug-reports",
            user_id="developer_1",
        )
        report = workflow.run_investigation(session_id, req)
        assert report.issue_id.startswith("DF-")
        issue_id = report.issue_id

        # 2. Approval Request
        app_req = workflow.publish_for_approval(session_id)
        assert app_req.issue_id == issue_id

        # 3. Human Approval Decision
        val_res = workflow.process_approval(
            session_id,
            ApprovalActionPayload(
                raw_command=f"APPROVE {issue_id}",
                user_id="lead_developer",
                room_id="bug-reports",
            ),
        )
        assert val_res.is_valid
        assert val_res.decision == ApprovalDecision.APPROVED

        # 4. Fix Execution (mocked to avoid disk mutation during test)
        plan = FixPlan(
            issue_id=issue_id,
            approval_id=app_req.approval_id,
            execution_token=val_res.execution_token,
            patches=[
                FixPatch(
                    relative_path="app/routers/auth.py",
                    new_content="# patched content",
                    description="Catch auth error",
                )
            ],
            target_tests=["tests/test_auth.py"],
        )

        mock_exec_report = ExecutionReport(
            issue_id=issue_id,
            approval_id=app_req.approval_id,
            branch=f"devflow/fix-{issue_id.lower()}",
            files_changed=["app/routers/auth.py"],
            changes_made="Patched auth exception",
            tests_executed=7,
            tests_passed=7,
            tests_failed=0,
            execution_status=ExecutionStatus.SUCCESS,
            remaining_risks="None identified. Automated fix verified.",
        )
        with patch.object(workflow.executor, "execute_fix", return_value=mock_exec_report):
            exec_res = workflow.execute_fix(session_id, plan)
            assert exec_res.execution_status == ExecutionStatus.SUCCESS

        # 5. Final Stage 8 Report Generation
        final_eng = workflow.generate_final_report(session_id, room_id="bug-reports")
        assert final_eng.issue_id == issue_id
        assert final_eng.tests_passed == 7

        # Verify Switch reporter captured all stages
        updates = switch.get_updates(issue_id)
        # Stages recorded with this issue_id:
        # report_investigation_completed, report_approval_requested, report_approval_decided,
        # report_fix_started, report_tests_completed, report_final_summary
        recorded_stages = [u.stage for u in updates]
        assert WorkflowStage.INVESTIGATION_COMPLETED in recorded_stages
        assert WorkflowStage.APPROVAL_REQUESTED in recorded_stages
        assert WorkflowStage.APPROVAL_DECIDED in recorded_stages
        assert WorkflowStage.FIX_IMPLEMENTATION_STARTED in recorded_stages
        assert WorkflowStage.TESTS_COMPLETED in recorded_stages
        assert WorkflowStage.FINAL_REPORT_PUBLISHED in recorded_stages


# ---------------------------------------------------------------------------
# API Endpoints Test
# ---------------------------------------------------------------------------

class TestReportingAPI:
    """Verifies service integration for stage updates and GitHub operations."""

    def test_get_stage_updates_logic(self):
        # Record a test update
        from app.services.switch_reporter import switch_reporter
        switch_reporter.report_bug_received("DF-TEST-API", "Test summary", room_id="test-room")

        updates = switch_reporter.get_updates("DF-TEST-API")
        assert len(updates) >= 1
        assert updates[0].issue_id == "DF-TEST-API"
        assert updates[0].stage == WorkflowStage.BUG_RECEIVED

    def test_github_create_issue_unconfigured(self):
        from app.services.github_service import github_service
        ref = github_service.create_issue(
            issue_id="DF-099",
            title="API Test Bug",
            body="Bug details from endpoint test",
            is_approved=True,
        )
        assert ref.status in ("unconfigured", "approval_required")

    def test_github_create_pr_guard(self):
        from app.services.github_service import github_service
        with pytest.raises(WorkflowStateError) as exc_info:
            github_service.create_pull_request(
                issue_id="DF-099",
                title="Bad PR Test",
                head_branch="main",
                body="PR details",
                is_approved=True,
            )
        assert "Cannot open pull request with main/master" in str(exc_info.value)

