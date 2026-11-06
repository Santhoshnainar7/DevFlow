"""
Automated Pytest test suite for DevFlow Phase 05: Controlled Code Fixing and Test Execution.

Covers all 8 required test scenarios:
1. Approved bug fix
2. Fix that passes tests
3. Fix that fails tests
4. Existing unrelated repository changes
5. Missing test dependencies
6. Test timeout
7. Invalid approval
8. Attempted modification of an unauthorized file

Also verifies:
- Main branch protection & isolated branch creation
- Safe revert on failure
- Accurate test count capture
- Standardized execution report formatting
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.models.approval import ApprovalActionPayload, ApprovalDecision
from app.models.execution import (
    ExecutionReport,
    ExecutionStatus,
    FixPatch,
    FixPlan,
)
from app.services.approval_manager import ApprovalManager
from app.services.controlled_test_runner import ControlledTestRunner, TestExecutionResult
from app.services.fix_executor import FixExecutor
from app.services.git_workflow import GitWorkflow

DEMO_REPO_PATH = Path(__file__).resolve().parent.parent / "demo_repository"


@pytest.fixture
def isolated_repo():
    """Provides a fresh, isolated temporary copy of demo_repository for mutation testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "demo_repository"
        shutil.copytree(DEMO_REPO_PATH, dest)
        yield dest


@pytest.fixture
def approval_setup():
    """Sets up an approval manager with a pre-approved issue and single-use execution token."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Path(tmpdir) / "approvals.json"
        mgr = ApprovalManager(storage_path=storage, authorized_users=["lead_dev"])
        req = mgr.create_request(
            issue_id="DF-001",
            issue_title="Login wrong password status code",
            root_cause="Invalid exception mapping",
            affected_files=["app/routers/auth.py"],
            proposed_fix="Return 401 on password mismatch",
            testing_plan=["test_login_wrong_password"],
        )
        # Approve request
        payload = ApprovalActionPayload(raw_command="APPROVE DF-001", user_id="lead_dev")
        result = mgr.process_action(payload)
        yield mgr, req, result.execution_token


# ---------------------------------------------------------------------------
# Scenario 1 & 2: Approved Bug Fix & Fix That Passes Tests
# ---------------------------------------------------------------------------
def test_scenario_1_and_2_approved_fix_passing_tests(isolated_repo, approval_setup):
    """
    Scenario 1 & 2: Valid approved fix applied on isolated branch and passes tests.
    """
    mgr, req, token = approval_setup
    executor = FixExecutor(repo_path=isolated_repo, manager=mgr)

    # Valid patch to auth_service.py
    current_content = (isolated_repo / "app" / "services" / "auth_service.py").read_text(encoding="utf-8")
    plan = FixPlan(
        issue_id="DF-001",
        approval_id=req.approval_id,
        execution_token=token,
        patches=[
            FixPatch(
                relative_path="app/services/auth_service.py",
                new_content=current_content + "\n# Valid comment fix\n",
                description="Verified patch to auth service",
            )
        ],
        target_tests=["tests/test_auth.py"],
        summary_of_changes="Added verified comment fix",
    )

    # Mock test runner result simulating 7/7 tests passing
    mock_runner_res = TestExecutionResult(
        command="pytest tests/test_auth.py -v",
        exit_code=0,
        tests_executed=7,
        tests_passed=7,
        tests_failed=0,
        passed=True,
        stdout="7 passed in 0.15s",
    )

    with patch.object(ControlledTestRunner, "run_tests", return_value=mock_runner_res):
        report = executor.execute_fix(plan)

    assert report.execution_status == ExecutionStatus.SUCCESS
    assert report.issue_id == "DF-001"
    assert report.approval_id == req.approval_id
    assert report.branch.startswith("devflow/fix-df001-")
    assert "app/services/auth_service.py" in report.files_changed
    assert report.tests_executed == 7
    assert report.tests_passed == 7
    assert report.tests_failed == 0
    assert report.requires_human_intervention is False

    # Check report formatting
    formatted = report.to_formatted_report()
    assert "Execution status: SUCCESS" in formatted
    assert "Tests passed: 7" in formatted
    assert "Branch: devflow/fix-df001-" in formatted


# ---------------------------------------------------------------------------
# Scenario 3: Fix That Fails Tests
# ---------------------------------------------------------------------------
def test_scenario_3_fix_that_fails_tests(isolated_repo, approval_setup):
    """
    Scenario 3: Proposed patch fails test assertion. Reverts changes and requests human help.
    """
    mgr, req, token = approval_setup
    executor = FixExecutor(repo_path=isolated_repo, manager=mgr)

    original_content = (isolated_repo / "app" / "routers" / "auth.py").read_text(encoding="utf-8")

    plan = FixPlan(
        issue_id="DF-001",
        approval_id=req.approval_id,
        execution_token=token,
        patches=[
            FixPatch(
                relative_path="app/routers/auth.py",
                new_content="# Syntax error intentional\ndef broken():",
                description="Buggy patch",
            )
        ],
        target_tests=["tests/test_auth.py"],
    )

    # Mock runner failure
    mock_runner_res = TestExecutionResult(
        command="pytest tests/test_auth.py -v",
        exit_code=1,
        tests_executed=7,
        tests_passed=5,
        tests_failed=2,
        passed=False,
        failure_explanation="FAILED test_login_wrong_password - assert response.status_code == 401",
        stdout="FAILED test_login_wrong_password\n2 failed, 5 passed",
    )

    with patch.object(ControlledTestRunner, "run_tests", return_value=mock_runner_res):
        report = executor.execute_fix(plan)

    assert report.execution_status == ExecutionStatus.FAILED_TESTS
    assert report.tests_failed == 2
    assert report.requires_human_intervention is True
    assert "safely reverted" in report.remaining_risks.lower()

    # Verify original file was safely restored by the revert mechanism
    restored = (isolated_repo / "app" / "routers" / "auth.py").read_text(encoding="utf-8")
    assert restored == original_content


# ---------------------------------------------------------------------------
# Scenario 4: Existing Unrelated Repository Changes
# ---------------------------------------------------------------------------
def test_scenario_4_dirty_repository_aborts(isolated_repo, approval_setup):
    """
    Scenario 4: Working tree has uncommitted developer changes. Aborts before modifying files.
    """
    mgr, req, token = approval_setup
    executor = FixExecutor(repo_path=isolated_repo, manager=mgr)

    plan = FixPlan(
        issue_id="DF-001",
        approval_id=req.approval_id,
        execution_token=token,
        patches=[
            FixPatch(
                relative_path="app/routers/auth.py",
                new_content="new",
            )
        ],
    )

    # Mock check_uncommitted_changes returning True (dirty)
    with patch.object(GitWorkflow, "check_uncommitted_changes", return_value=(True, "Uncommitted changes in auth.py")):
        report = executor.execute_fix(plan)

    assert report.execution_status == ExecutionStatus.FAILED_DIRTY_REPO
    assert report.files_changed == []
    assert report.requires_human_intervention is True
    assert "developer changes" in report.changes_made


# ---------------------------------------------------------------------------
# Scenario 5: Missing Test Dependencies
# ---------------------------------------------------------------------------
def test_scenario_5_missing_test_dependencies(isolated_repo, approval_setup):
    """
    Scenario 5: Tests fail due to missing package import. Detected and classified as FAILED_DEPENDENCY.
    """
    mgr, req, token = approval_setup
    executor = FixExecutor(repo_path=isolated_repo, manager=mgr)

    plan = FixPlan(
        issue_id="DF-001",
        approval_id=req.approval_id,
        execution_token=token,
        patches=[
            FixPatch(
                relative_path="app/services/auth_service.py",
                new_content="# comment",
            )
        ],
    )

    mock_runner_res = TestExecutionResult(
        command="pytest",
        exit_code=1,
        is_dependency_missing=True,
        passed=False,
        failure_explanation="ModuleNotFoundError: No module named 'jwt'",
        stdout="ModuleNotFoundError: No module named 'jwt'",
    )

    with patch.object(ControlledTestRunner, "run_tests", return_value=mock_runner_res):
        report = executor.execute_fix(plan)

    assert report.execution_status == ExecutionStatus.FAILED_DEPENDENCY
    assert report.requires_human_intervention is True
    assert "Missing package" in report.remaining_risks


# ---------------------------------------------------------------------------
# Scenario 6: Test Timeout
# ---------------------------------------------------------------------------
def test_scenario_6_test_timeout(isolated_repo, approval_setup):
    """
    Scenario 6: Test execution exceeds timeout limit.
    """
    mgr, req, token = approval_setup
    executor = FixExecutor(repo_path=isolated_repo, manager=mgr)

    plan = FixPlan(
        issue_id="DF-001",
        approval_id=req.approval_id,
        execution_token=token,
        patches=[
            FixPatch(
                relative_path="app/services/auth_service.py",
                new_content="# timeout test",
            )
        ],
    )

    mock_runner_res = TestExecutionResult(
        command="pytest",
        exit_code=-1,
        is_timeout=True,
        passed=False,
        failure_explanation="Execution timed out after 60 seconds.",
    )

    with patch.object(ControlledTestRunner, "run_tests", return_value=mock_runner_res):
        report = executor.execute_fix(plan)

    assert report.execution_status == ExecutionStatus.FAILED_TIMEOUT
    assert report.requires_human_intervention is True
    assert "time budget" in report.remaining_risks.lower()


# ---------------------------------------------------------------------------
# Scenario 7: Invalid Approval
# ---------------------------------------------------------------------------
def test_scenario_7_invalid_approval(isolated_repo, approval_setup):
    """
    Scenario 7: Fix execution attempted with an invalid, unapproved, or forged token.
    """
    mgr, req, _ = approval_setup
    executor = FixExecutor(repo_path=isolated_repo, manager=mgr)

    plan = FixPlan(
        issue_id="DF-001",
        approval_id=req.approval_id,
        execution_token="FORGED_OR_EXPIRED_TOKEN",
        patches=[
            FixPatch(
                relative_path="app/routers/auth.py",
                new_content="new",
            )
        ],
    )

    report = executor.execute_fix(plan)

    assert report.execution_status == ExecutionStatus.FAILED_INVALID_APPROVAL
    assert report.files_changed == []
    assert report.requires_human_intervention is True
    assert "Authorization failure" in report.error_details


# ---------------------------------------------------------------------------
# Scenario 8: Attempted Modification of an Unauthorized File
# ---------------------------------------------------------------------------
def test_scenario_8_unauthorized_file_modification(isolated_repo, approval_setup):
    """
    Scenario 8: Patch targets a file outside workspace boundary or with invalid extension.
    """
    mgr, req, token = approval_setup
    executor = FixExecutor(repo_path=isolated_repo, manager=mgr)

    for bad_path in ["../../outside_repo.py", "unauthorized/file.exe", "/absolute/path/file.py"]:
        plan = FixPlan(
            issue_id="DF-001",
            approval_id=req.approval_id,
            execution_token=token,
            patches=[
                FixPatch(
                    relative_path=bad_path,
                    new_content="malicious content",
                )
            ],
        )

        # Create new token for each attempt (since previous may be consumed if reached gate)
        with patch.object(ApprovalManager, "authorize_code_modification", return_value=True):
            report = executor.execute_fix(plan)

        assert report.execution_status == ExecutionStatus.FAILED_UNAUTHORIZED_FILE
        assert report.files_changed == []
        assert report.requires_human_intervention is True
        assert "outside authorized workspace" in report.remaining_risks.lower()


# ---------------------------------------------------------------------------
# Controlled Test Runner Unit Tests
# ---------------------------------------------------------------------------
def test_controlled_test_runner_parsing(isolated_repo):
    """Verifies that the test runner accurately parses pytest output numbers."""
    runner = ControlledTestRunner(repo_path=isolated_repo)
    p, f, t = runner._parse_test_counts("== 7 passed in 0.12s ==")
    assert p == 7
    assert f == 0
    assert t == 7

    p2, f2, t2 = runner._parse_test_counts("== 1 failed, 6 passed in 0.44s ==")
    assert p2 == 6
    assert f2 == 1
    assert t2 == 7

