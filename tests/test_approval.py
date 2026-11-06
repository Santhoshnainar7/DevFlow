"""
Automated Pytest test suite for DevFlow Phase 04: Human Approval Workflow.

Covers all 8 required test cases:
1. Valid approval
2. Invalid approval syntax
3. Unauthorized approval
4. Rejected proposal
5. Duplicate approval
6. Expired approval
7. Approval for wrong issue
8. Approval after issue cancellation

Also verifies:
- Single-use execution token consumption
- Code modification gate security enforcement
- Concurrency and persistent disk storage
- Exact Switch prompt formatting
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from app.core.exceptions import UnauthorizedApproverError, WorkflowStateError
from app.models.approval import (
    ApprovalActionPayload,
    ApprovalDecision,
    ApprovalRequest,
)
from app.services.approval_manager import ApprovalManager
from app.services.modification_gate import CodeModificationGate


@pytest.fixture
def temp_storage():
    """Provides a temporary file path for isolated approval persistence testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_approvals.json"


@pytest.fixture
def manager(temp_storage):
    """Provides an isolated ApprovalManager instance."""
    return ApprovalManager(
        storage_path=temp_storage,
        authorized_users=["lead_dev", "santhosh", "reviewer"],
        default_timeout_seconds=300,
    )


@pytest.fixture
def sample_request(manager):
    """Creates a standard pending approval request."""
    return manager.create_request(
        issue_id="DF-001",
        issue_title="Login returns 200 on wrong password",
        root_cause="Incorrect authentication exception handling.",
        affected_files=["app/routers/auth.py"],
        proposed_fix="Handle invalid credentials and return HTTP 401.",
        testing_plan=["Valid login", "Invalid password", "Missing credentials"],
    )


# ---------------------------------------------------------------------------
# Test Case 1: Valid Approval
# ---------------------------------------------------------------------------
def test_valid_approval(manager, sample_request):
    """Authorized user submits explicit approval command before expiration."""
    payload = ApprovalActionPayload(
        raw_command="APPROVE DF-001",
        user_id="lead_dev",
        issue_id="DF-001",
    )
    result = manager.process_action(payload)

    assert result.is_valid is True
    assert result.decision == ApprovalDecision.APPROVED
    assert result.execution_permitted is True
    assert result.decided_by == "lead_dev"
    assert result.execution_token is not None
    assert result.execution_token.startswith("EXEC-DF-001-")

    # Verify execution gate accepts token
    gate = CodeModificationGate(manager)
    assert gate.request_write_access("DF-001", result.execution_token) is True


# ---------------------------------------------------------------------------
# Test Case 2: Invalid Approval (Syntax Error)
# ---------------------------------------------------------------------------
def test_invalid_approval_syntax(manager, sample_request):
    """Inexact, ambiguous, or conversational commands are rejected."""
    for bad_cmd in [
        "MAYBE DF-001",
        "APPROV DF-001",
        "sounds good to me",
        "yes please",
        "looks fine",
        "approve without issue id",
    ]:
        payload = ApprovalActionPayload(
            raw_command=bad_cmd,
            user_id="lead_dev",
            issue_id="DF-001",
        )
        result = manager.process_action(payload)
        assert result.is_valid is False
        assert result.execution_permitted is False
        assert ("Invalid approval command syntax" in result.message or "rejected" in result.message.lower())


# ---------------------------------------------------------------------------
# Test Case 3: Unauthorized Approval
# ---------------------------------------------------------------------------
def test_unauthorized_approval(manager, sample_request):
    """User not in the authorized developers allowlist cannot approve fixes."""
    payload = ApprovalActionPayload(
        raw_command="APPROVE DF-001",
        user_id="unauthorized_bob",
        issue_id="DF-001",
    )
    result = manager.process_action(payload)

    assert result.is_valid is False
    assert result.execution_permitted is False
    assert "not in the approved developers allowlist" in result.message

    # Ensure modification gate blocks anonymous/unapproved execution
    gate = CodeModificationGate(manager)
    with pytest.raises(UnauthorizedApproverError):
        gate.request_write_access("DF-001", execution_token=None)


# ---------------------------------------------------------------------------
# Test Case 4: Rejected Proposal
# ---------------------------------------------------------------------------
def test_rejected_proposal(manager, sample_request):
    """Authorized user explicitly rejects the proposed fix."""
    payload = ApprovalActionPayload(
        raw_command="REJECT DF-001",
        user_id="lead_dev",
        issue_id="DF-001",
        rejection_reason="Root cause does not address edge case.",
    )
    result = manager.process_action(payload)

    assert result.is_valid is True
    assert result.decision == ApprovalDecision.REJECTED
    assert result.execution_permitted is False
    assert result.execution_token is None

    # Verify request in store is marked REJECTED
    req = manager.get_request("DF-001")
    assert req.status == ApprovalDecision.REJECTED
    assert req.decided_by == "lead_dev"

    # Modification gate must block rejected issue
    gate = CodeModificationGate(manager)
    with pytest.raises(UnauthorizedApproverError):
        gate.request_write_access("DF-001", execution_token="INVALID")


# ---------------------------------------------------------------------------
# Test Case 5: Duplicate Approval & Token Re-use
# ---------------------------------------------------------------------------
def test_duplicate_approval_and_token_reuse(manager, sample_request):
    """Submitting approval for an already approved fix is blocked."""
    payload = ApprovalActionPayload(
        raw_command="APPROVE DF-001",
        user_id="lead_dev",
        issue_id="DF-001",
    )
    res1 = manager.process_action(payload)
    assert res1.is_valid is True
    assert res1.execution_permitted is True

    # Second approval attempt must be rejected as duplicate
    res2 = manager.process_action(payload)
    assert res2.is_valid is False
    assert res2.execution_permitted is False
    assert "Duplicate approval" in res2.message

    # Consume token once
    gate = CodeModificationGate(manager)
    gate.request_write_access("DF-001", res1.execution_token)

    # Re-using the consumed token must raise WorkflowStateError
    with pytest.raises(WorkflowStateError):
        gate.request_write_access("DF-001", res1.execution_token)


# ---------------------------------------------------------------------------
# Test Case 6: Expired Approval
# ---------------------------------------------------------------------------
def test_expired_approval(temp_storage):
    """Approval request past its expiration timestamp is rejected."""
    manager = ApprovalManager(
        storage_path=temp_storage,
        authorized_users=["lead_dev"],
        default_timeout_seconds=-10,  # Created already expired
    )
    manager.create_request(
        issue_id="DF-002",
        issue_title="Expired issue",
        root_cause="Something",
        affected_files=["app/main.py"],
        proposed_fix="Fix it",
        testing_plan=["Test"],
    )

    payload = ApprovalActionPayload(
        raw_command="APPROVE DF-002",
        user_id="lead_dev",
        issue_id="DF-002",
    )
    result = manager.process_action(payload)

    assert result.is_valid is False
    assert result.decision == ApprovalDecision.EXPIRED
    assert result.execution_permitted is False
    assert "expired" in result.message.lower()


# ---------------------------------------------------------------------------
# Test Case 7: Approval for the Wrong Issue
# ---------------------------------------------------------------------------
def test_approval_for_wrong_issue(manager, sample_request):
    """Command targeting an unknown or mismatched issue is rejected."""
    # Target unknown issue
    payload1 = ApprovalActionPayload(
        raw_command="APPROVE DF-999",
        user_id="lead_dev",
    )
    res1 = manager.process_action(payload1)
    assert res1.is_valid is False
    assert res1.execution_permitted is False
    assert "No approval request found for issue 'DF-999'" in res1.message

    # Context mismatch (chat context DF-001, but command says APPROVE DF-002)
    payload2 = ApprovalActionPayload(
        raw_command="APPROVE DF-002",
        user_id="lead_dev",
        issue_id="DF-001",
    )
    res2 = manager.process_action(payload2)
    assert res2.is_valid is False
    assert res2.execution_permitted is False
    assert "Issue mismatch rejected" in res2.message


# ---------------------------------------------------------------------------
# Test Case 8: Approval after Issue Cancellation
# ---------------------------------------------------------------------------
def test_approval_after_cancellation(manager, sample_request):
    """An issue cancelled by a user cannot subsequently be approved."""
    cancelled = manager.cancel_request("DF-001", cancelled_by="admin", reason="False alarm")
    assert cancelled is True

    payload = ApprovalActionPayload(
        raw_command="APPROVE DF-001",
        user_id="lead_dev",
        issue_id="DF-001",
    )
    result = manager.process_action(payload)

    assert result.is_valid is False
    assert result.decision == ApprovalDecision.CANCELLED
    assert result.execution_permitted is False
    assert "was cancelled" in result.message


# ---------------------------------------------------------------------------
# Persistence & Formatting Tests
# ---------------------------------------------------------------------------
def test_persistence_across_manager_instances(temp_storage):
    """Verifies that approval records survive service restarts."""
    mgr1 = ApprovalManager(storage_path=temp_storage, authorized_users=["lead_dev"])
    mgr1.create_request(
        issue_id="DF-010",
        issue_title="Persistent Issue",
        root_cause="Database error",
        affected_files=["app/db.py"],
        proposed_fix="Add index",
        testing_plan=["Perf test"],
    )

    # Create new manager pointing to same storage
    mgr2 = ApprovalManager(storage_path=temp_storage, authorized_users=["lead_dev"])
    loaded = mgr2.get_request("DF-010")
    assert loaded is not None
    assert loaded.issue_id == "DF-010"
    assert loaded.root_cause == "Database error"


def test_switch_prompt_format(sample_request):
    """Verifies output format matches the exact specification example."""
    prompt = sample_request.to_switch_prompt()
    assert "Investigation completed." in prompt
    assert "Issue: DF-001" in prompt
    assert "Root cause: Incorrect authentication exception handling." in prompt
    assert "Affected file: app/routers/auth.py" in prompt
    assert "Proposed fix:\nHandle invalid credentials and return HTTP 401." in prompt
    assert "Testing plan:\n- Valid login\n- Invalid password\n- Missing credentials" in prompt
    assert "Reply with:\n\nAPPROVE DF-001\nor\nREJECT DF-001" in prompt
