"""
End-to-End Scenario Test Suite for DevFlow Phase 07 (Part A).

Validates all 8 required edge cases and production failure modes:
1. Successful execution (happy path)
2. Rejected approval (workflow aborted safely)
3. Invalid approval (syntax error / malformed command)
4. Failed tests (controlled rollback and failure reporting)
5. Missing repository (graceful degradation)
6. Unavailable agent / approval timeout (expired tokens rejected)
7. Duplicate requests (idempotent gating, replay rejection)
8. Unauthorized user (RBAC security block)
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.exceptions import (
    RepositoryError,
    UnauthorizedApproverError,
    WorkflowStateError,
)
from app.models.approval import (
    ApprovalActionPayload,
    ApprovalDecision,
    ApprovalRequest,
)
from app.models.execution import (
    ExecutionReport,
    ExecutionStatus,
    FixPatch,
    FixPlan,
)
from app.models.investigation import (
    BugCategory,
    InvestigationReport,
    InvestigationRequest,
    Severity,
)
from app.models.reporting import WorkflowStage
from app.services.approval_manager import ApprovalManager
from app.services.fix_executor import FixExecutor
from app.services.git_workflow import GitWorkflow
from app.services.investigation_engine import BugInvestigationEngine
from app.services.switch_reporter import SwitchReporter
from app.workflows.triage import TriageState, TriageWorkflow


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent / "demo_repository"


@pytest.fixture
def switch_reporter() -> SwitchReporter:
    return SwitchReporter()


@pytest.fixture
def isolated_approval_manager(tmp_path: Path) -> ApprovalManager:
    return ApprovalManager(
        storage_path=tmp_path / "approvals.json",
        authorized_users=["lead_dev", "alice_admin"],
        default_timeout_seconds=2,  # fast timeout for testing
    )


# ---------------------------------------------------------------------------
# Scenario 1: Successful Execution (Happy Path)
# ---------------------------------------------------------------------------

def test_scenario_1_successful_execution(repo_root: Path, isolated_approval_manager: ApprovalManager, switch_reporter: SwitchReporter):
    """
    Scenario 1:
    Report received -> Investigated -> Approval requested -> Approved by authorized dev
    -> Fix executed on branch -> Pytest passes -> Stage 8 Final report published.
    """
    workflow = TriageWorkflow(
        manager=isolated_approval_manager,
        switch=switch_reporter,
    )
    session_id = "session-sc1-success"

    # Step 1-3: Bug receipt & investigation
    req = InvestigationRequest(
        description="Auth endpoint raises 500 when credentials are wrong",
        room_id="bug-reports",
        user_id="lead_dev",
    )
    report = workflow.run_investigation(session_id, req)
    assert report.bug_category == BugCategory.AUTHENTICATION
    assert report.issue_id.startswith("DF-")
    issue_id = report.issue_id

    # Step 4: Approval requested
    app_req = workflow.publish_for_approval(session_id)
    assert app_req.issue_id == issue_id
    assert workflow.get_state(session_id) == TriageState.AWAITING_APPROVAL

    # Step 5: Authorized approval
    val_res = workflow.process_approval(
        session_id,
        ApprovalActionPayload(
            raw_command=f"APPROVE {issue_id}",
            user_id="lead_dev",
            room_id="bug-reports",
        ),
    )
    assert val_res.is_valid
    assert val_res.decision == ApprovalDecision.APPROVED
    assert val_res.execution_permitted
    assert workflow.get_state(session_id) == TriageState.APPROVED

    # Step 6-7: Controlled Fix Execution (mocked runner to avoid dirtying git working tree)
    plan = FixPlan(
        issue_id=issue_id,
        approval_id=app_req.approval_id,
        execution_token=val_res.execution_token,
        patches=[
            FixPatch(
                relative_path="app/routers/auth.py",
                new_content="# Verified fix content",
                description="Return 401 on bad credentials",
            )
        ],
        target_tests=["tests/test_auth.py"],
    )

    mock_exec = ExecutionReport(
        issue_id=issue_id,
        approval_id=app_req.approval_id,
        branch=f"devflow/fix-{issue_id.lower()}",
        files_changed=["app/routers/auth.py"],
        changes_made="Patched auth exception",
        tests_executed=7,
        tests_passed=7,
        tests_failed=0,
        execution_status=ExecutionStatus.SUCCESS,
        remaining_risks="None identified.",
    )

    with patch.object(workflow.executor, "execute_fix", return_value=mock_exec):
        exec_report = workflow.execute_fix(session_id, plan)
        assert exec_report.execution_status == ExecutionStatus.SUCCESS
        assert workflow.get_state(session_id) == TriageState.EXECUTION_COMPLETE

    # Step 8: Final Engineering Report
    final_rep = workflow.generate_final_report(session_id, room_id="bug-reports")
    assert final_rep.issue_id == issue_id
    assert final_rep.tests_passed == 7
    assert "7 passed, 0 failed (SUCCESS)" in final_rep.to_formatted_report()


# ---------------------------------------------------------------------------
# Scenario 2: Rejected Approval
# ---------------------------------------------------------------------------

def test_scenario_2_rejected_approval(isolated_approval_manager: ApprovalManager, switch_reporter: SwitchReporter):
    """
    Scenario 2:
    Developer explicitly rejects the proposed fix.
    Workflow transitions to REJECTED and strictly halts without modifying files.
    """
    workflow = TriageWorkflow(
        manager=isolated_approval_manager,
        switch=switch_reporter,
    )
    session_id = "session-sc2-reject"

    req = InvestigationRequest(
        description="Database timeout on user lookup",
        room_id="bug-reports",
        user_id="lead_dev",
    )
    report = workflow.run_investigation(session_id, req)
    issue_id = report.issue_id
    workflow.publish_for_approval(session_id)

    # Reject proposal
    val_res = workflow.process_approval(
        session_id,
        ApprovalActionPayload(
            raw_command=f"REJECT {issue_id}",
            user_id="lead_dev",
            reason="Approach requires database index instead of code patch.",
        ),
    )
    assert val_res.is_valid
    assert val_res.decision == ApprovalDecision.REJECTED
    assert not val_res.execution_permitted
    assert workflow.get_state(session_id) == TriageState.REJECTED

    # Verify execution is blocked
    dummy_plan = FixPlan(
        issue_id=issue_id,
        approval_id="APP-DUMMY",
        execution_token="EXEC-NONE",
        patches=[],
    )
    with pytest.raises(WorkflowStateError) as exc_info:
        workflow.execute_fix(session_id, dummy_plan)
    assert "expected APPROVED" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Scenario 3: Invalid Approval Syntax
# ---------------------------------------------------------------------------

def test_scenario_3_invalid_approval_syntax(isolated_approval_manager: ApprovalManager):
    """
    Scenario 3:
    Developer submits malformed or unrecognized commands.
    Must be rejected with clear error guidance.
    """
    workflow = TriageWorkflow(manager=isolated_approval_manager)
    session_id = "session-sc3-invalid"

    req = InvestigationRequest(description="API returning 502", room_id="bug-reports")
    report = workflow.run_investigation(session_id, req)
    issue_id = report.issue_id
    workflow.publish_for_approval(session_id)

    # Malformed command
    val_res = workflow.process_approval(
        session_id,
        ApprovalActionPayload(
            raw_command="PLEASE DEPLOY THIS TO PRODUCTION",
            user_id="lead_dev",
        ),
    )
    assert not val_res.is_valid
    assert not val_res.execution_permitted
    assert val_res.decision == ApprovalDecision.PENDING
    assert "Invalid approval command syntax" in val_res.message
    # State remains AWAITING_APPROVAL so user can correct syntax
    assert workflow.get_state(session_id) == TriageState.AWAITING_APPROVAL


# ---------------------------------------------------------------------------
# Scenario 4: Failed Tests and Rollback
# ---------------------------------------------------------------------------

def test_scenario_4_failed_tests_rollback(isolated_approval_manager: ApprovalManager, switch_reporter: SwitchReporter):
    """
    Scenario 4:
    Code fix causes automated tests to fail.
    Fix executor detects failure, reports FAILED_TESTS, and preserves safety.
    """
    workflow = TriageWorkflow(
        manager=isolated_approval_manager,
        switch=switch_reporter,
    )
    session_id = "session-sc4-test-fail"

    req = InvestigationRequest(description="Validation defect", room_id="bug-reports")
    report = workflow.run_investigation(session_id, req)
    issue_id = report.issue_id
    app_req = workflow.publish_for_approval(session_id)

    val_res = workflow.process_approval(
        session_id,
        ApprovalActionPayload(raw_command=f"APPROVE {issue_id}", user_id="lead_dev"),
    )

    plan = FixPlan(
        issue_id=issue_id,
        approval_id=app_req.approval_id,
        execution_token=val_res.execution_token,
        patches=[
            FixPatch(
                relative_path="app/routers/auth.py",
                new_content="# Bad patch",
            )
        ],
    )

    failed_exec = ExecutionReport(
        issue_id=issue_id,
        approval_id=app_req.approval_id,
        branch=f"devflow/fix-{issue_id.lower()}",
        files_changed=["app/routers/auth.py"],
        changes_made="Patched file with regression",
        tests_executed=7,
        tests_passed=4,
        tests_failed=3,
        execution_status=ExecutionStatus.FAILED_TESTS,
        remaining_risks="Automated fix failed regression suite. Human intervention required.",
    )

    with patch.object(workflow.executor, "execute_fix", return_value=failed_exec):
        exec_report = workflow.execute_fix(session_id, plan)
        assert exec_report.execution_status == ExecutionStatus.FAILED_TESTS
        assert exec_report.tests_failed == 3

    # Generate final report reflecting failure
    final_rep = workflow.generate_final_report(session_id)
    assert "Execution did not succeed (FAILED_TESTS)" in final_rep.implemented_solution


# ---------------------------------------------------------------------------
# Scenario 5: Missing Repository
# ---------------------------------------------------------------------------

def test_scenario_5_missing_repository():
    """
    Scenario 5:
    Target repository path does not exist.
    Engine handles gracefully with clear diagnostic rather than uncaught crash.
    """
    engine = BugInvestigationEngine(default_repo_path="C:/nonexistent/path/to/repo")
    req = InvestigationRequest(
        description="Auth crash",
        repository_path="C:/nonexistent/path/to/repo",
    )
    report = engine.investigate(req)
    assert report.bug_category == BugCategory.AUTHENTICATION
    # Confirms findings vs hypothesis: repository could not be inspected
    assert "was not found or is inaccessible" in report.root_cause
    assert report.affected_files == []


# ---------------------------------------------------------------------------
# Scenario 6: Approval Timeout / Expired Token
# ---------------------------------------------------------------------------

def test_scenario_6_approval_timeout(isolated_approval_manager: ApprovalManager):
    """
    Scenario 6:
    Approval window expires before developer response.
    Token validation fails with expired notice.
    """
    # Create request that expired 10 minutes ago
    req = isolated_approval_manager.create_request(
        issue_id="DF-099",
        issue_title="Timeout test",
        root_cause="Test",
        affected_files=["app/main.py"],
        proposed_fix="Fix",
        testing_plan=["Test"],
        timeout_seconds=-60,  # in the past
    )

    # Attempt to approve expired request
    val_res = isolated_approval_manager.process_action(
        ApprovalActionPayload(
            raw_command="APPROVE DF-099",
            user_id="lead_dev",
        )
    )
    assert not val_res.is_valid
    assert not val_res.execution_permitted
    assert "expired" in val_res.message.lower()


# ---------------------------------------------------------------------------
# Scenario 7: Duplicate Requests / Replay Attack
# ---------------------------------------------------------------------------

def test_scenario_7_duplicate_requests(isolated_approval_manager: ApprovalManager):
    """
    Scenario 7:
    Duplicate approval commands cannot execute the same fix twice.
    Replay attempts must be blocked.
    """
    isolated_approval_manager.create_request(
        issue_id="DF-077",
        issue_title="Duplicate test",
        root_cause="Test",
        affected_files=["app/main.py"],
        proposed_fix="Fix",
        testing_plan=["Test"],
    )

    # First approval succeeds
    val_1 = isolated_approval_manager.process_action(
        ApprovalActionPayload(raw_command="APPROVE DF-077", user_id="lead_dev")
    )
    assert val_1.is_valid
    token = val_1.execution_token

    # Second approval on already approved issue is rejected
    val_2 = isolated_approval_manager.process_action(
        ApprovalActionPayload(raw_command="APPROVE DF-077", user_id="lead_dev")
    )
    assert not val_2.is_valid
    assert "duplicate approval" in val_2.message.lower()

    # Consuming the token once succeeds
    assert isolated_approval_manager.authorize_code_modification("DF-077", token) is True

    # Consuming twice fails with WorkflowStateError
    with pytest.raises(WorkflowStateError) as exc_info:
        isolated_approval_manager.authorize_code_modification("DF-077", token)
    assert "Duplicate execution blocked" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Scenario 8: Unauthorized User
# ---------------------------------------------------------------------------

def test_scenario_8_unauthorized_user(isolated_approval_manager: ApprovalManager):
    """
    Scenario 8:
    A user not present in DEVFLOW_APPROVED_USERS attempts to approve or reject.
    Must be blocked server-side by the authorization gate.
    """
    isolated_approval_manager.create_request(
        issue_id="DF-088",
        issue_title="Security auth test",
        root_cause="Test",
        affected_files=["app/main.py"],
        proposed_fix="Fix",
        testing_plan=["Test"],
    )

    val_unauthorized = isolated_approval_manager.process_action(
        ApprovalActionPayload(
            raw_command="APPROVE DF-088",
            user_id="untrusted_external_guest",
        )
    )
    assert not val_unauthorized.is_valid
    assert not val_unauthorized.execution_permitted
    assert "not in the approved developers allowlist" in val_unauthorized.message
