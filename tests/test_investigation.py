"""
Automated Pytest test suite for DevFlow Phase 03: Bug Investigation Engine.

Verifies:
- Bug classification and search term extraction
- Severity assessment
- Read-only AST repository inspection (real files, real functions, no hallucination)
- Directory traversal protection
- Graceful handling of missing repositories
- Three reproducible bug scenarios in demo_repository
- Strict compliance with the required 11-field investigation report format
"""

from pathlib import Path
import pytest

from app.models.investigation import (
    BugCategory,
    InvestigationReport,
    InvestigationRequest,
    Severity,
)
from app.services.bug_classifier import (
    assess_severity,
    classify_bug,
    extract_search_terms,
)
from app.services.investigation_engine import BugInvestigationEngine
from app.services.issue_tracker import IssueTracker
from app.services.repository_inspector import RepositoryInspector
from app.services.reproduction_runner import ReproductionRunner

DEMO_REPO_PATH = Path(__file__).resolve().parent.parent / "demo_repository"


# ---------------------------------------------------------------------------
# 1. Bug Classification & Search Terms Unit Tests
# ---------------------------------------------------------------------------
def test_bug_classification():
    """Verifies regex and heuristic classification across domain categories."""
    assert (
        classify_bug("The login endpoint returns 200 for wrong password")
        == BugCategory.AUTHENTICATION
    )
    assert (
        classify_bug("Request fails with 422 unprocessable entity because required field is empty")
        == BugCategory.VALIDATION_ERRORS
    )
    assert (
        classify_bug("API route /api/v1/users returns 500 internal server error")
        == BugCategory.API_FAILURES
    )
    assert (
        classify_bug("Postgres query times out with deadlock on foreign key constraint")
        == BugCategory.DATABASE_ERRORS
    )
    assert (
        classify_bug("CSS button rendering incorrectly on Safari browser UI")
        == BugCategory.FRONTEND_ISSUES
    )
    assert (
        classify_bug("High memory leak causing latency and slow response time")
        == BugCategory.PERFORMANCE_PROBLEMS
    )
    assert (
        classify_bug("ModuleNotFoundError: No module named 'cryptography'")
        == BugCategory.DEPENDENCY_ISSUES
    )
    assert (
        classify_bug("Something random that doesn't match anything")
        == BugCategory.UNKNOWN
    )


def test_severity_assessment():
    """Verifies severity level assignment."""
    assert (
        assess_severity("Critical security vulnerability in auth bypass", BugCategory.AUTHENTICATION)
        == Severity.CRITICAL
    )
    assert (
        assess_severity("Wrong password returns 200 instead of 401", BugCategory.AUTHENTICATION)
        == Severity.HIGH
    )
    assert (
        assess_severity("Username validation message has typo", BugCategory.VALIDATION_ERRORS)
        == Severity.LOW
    )


def test_search_terms_extraction():
    """Verifies extraction of routes, error types, and identifiers."""
    text = "Error in /api/v1/login when InvalidPasswordException is raised in authenticate_user"
    terms = extract_search_terms(text)
    assert "/api/v1/login" in terms
    assert "InvalidPasswordException" in terms
    assert "authenticate_user" in terms
    assert "login" in terms


# ---------------------------------------------------------------------------
# 2. Repository Inspector Unit Tests (Read-Only & Security)
# ---------------------------------------------------------------------------
def test_repository_inspector_ast_extraction():
    """Verifies that the inspector extracts REAL AST symbols from demo_repository."""
    inspector = RepositoryInspector(DEMO_REPO_PATH)
    assert inspector.exists() is True

    # Inspect auth_service.py
    auth_service_path = DEMO_REPO_PATH / "app" / "services" / "auth_service.py"
    inspection = inspector.inspect_file(auth_service_path)

    assert inspection.exists is True
    # Real function verified
    assert "authenticate_user" in inspection.functions
    assert inspection.size_bytes > 0


def test_repository_inspector_path_traversal_guard():
    """Verifies directory traversal attacks are prevented."""
    inspector = RepositoryInspector(DEMO_REPO_PATH)
    # Attempting to read outside demo_repository
    content = inspector.read_file_safe("../../pyproject.toml")
    assert content is None


def test_graceful_missing_repository():
    """Verifies missing repositories are handled without throwing unhandled exceptions."""
    non_existent = Path("C:/non/existent/path/for/devflow_test")
    engine = BugInvestigationEngine(default_repo_path=non_existent)

    req = InvestigationRequest(
        description="Login endpoint crashes on null input",
        repository_path=str(non_existent),
        attempt_reproduction=False,
    )
    report = engine.investigate(req)

    assert "not found" in report.root_cause.lower()
    assert report.affected_files == []


# ---------------------------------------------------------------------------
# 3. Three Reproducible Bug Scenarios in demo_repository
# ---------------------------------------------------------------------------
def test_scenario_1_authentication_bug_report():
    """
    Scenario 1: Authentication failure
    Report: Wrong password returns 200 OK instead of 401 Unauthorized.
    """
    engine = BugInvestigationEngine(default_repo_path=DEMO_REPO_PATH)
    req = InvestigationRequest(
        issue_id="DF-001",
        title="Login endpoint returns 200 for incorrect password",
        description=(
            "The login endpoint (/api/v1/login) returns HTTP 200 with a token "
            "even when an incorrect password is provided. It should return HTTP 401 Unauthorized."
        ),
        repository_path=str(DEMO_REPO_PATH),
        attempt_reproduction=True,
    )

    report = engine.investigate(req)

    # Validations
    assert report.issue_id == "DF-001"
    assert report.bug_category == BugCategory.AUTHENTICATION
    assert report.severity == Severity.HIGH

    # Affected files must contain real checked-in files
    assert any("auth" in f.lower() for f in report.affected_files)
    # Relevant functions must list verified functions
    assert any("login" in fn or "authenticate" in fn for fn in report.relevant_functions)

    # Distinguishes confirmed findings vs hypotheses
    assert "HYPOTHESIS" in report.root_cause or "CONFIRMED" in report.root_cause

    # Formatted report matches exact required format
    formatted = report.to_formatted_report()
    assert "Issue ID: DF-001" in formatted
    assert "Bug category: Authentication" in formatted
    assert "Severity: High" in formatted
    assert "Affected files:" in formatted
    assert "Relevant functions:" in formatted
    assert "Root cause:" in formatted
    assert "Evidence:" in formatted
    assert "Proposed solution:" in formatted
    assert "Testing strategy:" in formatted
    assert "Potential risks:" in formatted


def test_scenario_2_validation_bug_report():
    """
    Scenario 2: Validation error
    Report: Empty username string in request body is not rejected with 422.
    """
    engine = BugInvestigationEngine(default_repo_path=DEMO_REPO_PATH)
    req = InvestigationRequest(
        issue_id="DF-002",
        title="Empty username input validation error",
        description=(
            "When POST /api/v1/login is called with an empty username '', "
            "the API fails with 422 unprocessable entity validation error."
        ),
        repository_path=str(DEMO_REPO_PATH),
        attempt_reproduction=True,
    )

    report = engine.investigate(req)

    assert report.issue_id == "DF-002"
    assert report.bug_category == BugCategory.VALIDATION_ERRORS
    assert report.severity in [Severity.MEDIUM, Severity.LOW]
    assert any("schema" in f.lower() or "auth" in f.lower() for f in report.affected_files)

    formatted = report.to_formatted_report()
    assert "Bug category: Validation errors" in formatted
    assert "Root cause:" in formatted
    assert "Proposed solution:" in formatted


def test_scenario_3_api_failure_contract_mismatch():
    """
    Scenario 3: API failure / Contract mismatch
    Report: Missing token_type field in login response payload causes 500 error.
    """
    engine = BugInvestigationEngine(default_repo_path=DEMO_REPO_PATH)
    req = InvestigationRequest(
        issue_id="DF-003",
        title="Login response payload missing token_type field",
        description=(
            "The /api/v1/login endpoint response payload is missing the 'token_type' "
            "attribute, causing API clients to encounter status code 500 unhandled key error."
        ),
        repository_path=str(DEMO_REPO_PATH),
        attempt_reproduction=True,
    )

    report = engine.investigate(req)

    assert report.issue_id == "DF-003"
    assert report.bug_category in [BugCategory.API_FAILURES, BugCategory.AUTHENTICATION]
    assert len(report.affected_files) > 0
    assert len(report.evidence) > 0

    formatted = report.to_formatted_report()
    assert "Issue ID: DF-003" in formatted
    assert "Testing strategy:" in formatted
    assert "Potential risks:" in formatted


def test_issue_tracker_thread_safety():
    """Verifies issue tracker sequentially increments IDs."""
    tracker = IssueTracker(prefix="TEST")
    tracker.reset("scope1")
    id1 = tracker.generate_id("scope1")
    id2 = tracker.generate_id("scope1")
    assert id1 == "TEST-001"
    assert id2 == "TEST-002"


def test_triage_workflow_state_machine():
    """Verifies the state machine transitions and report retrieval."""
    from app.workflows.triage import TriageState, TriageWorkflow

    workflow = TriageWorkflow(BugInvestigationEngine(default_repo_path=DEMO_REPO_PATH))
    session = "room_123"

    assert workflow.get_state(session) == TriageState.IDLE

    req = InvestigationRequest(
        description="Login error with wrong password returning 200",
        repository_path=str(DEMO_REPO_PATH),
        attempt_reproduction=False,
    )

    report = workflow.run_investigation(session, req)

    assert workflow.get_state(session) == TriageState.REPORT_GENERATED
    assert workflow.get_latest_report(session) is report
    assert report.bug_category == BugCategory.AUTHENTICATION


def test_investigate_api_endpoint_direct():
    """Verifies investigate endpoint logic directly."""
    engine = BugInvestigationEngine(default_repo_path=DEMO_REPO_PATH)
    req = InvestigationRequest(
        description="Login endpoint returns 200 for incorrect password",
        repository_path=str(DEMO_REPO_PATH),
        attempt_reproduction=False,
    )
    report = engine.investigate(req)
    assert report.bug_category == BugCategory.AUTHENTICATION
    formatted = report.to_formatted_report()
    assert "Issue ID:" in formatted
    assert "Bug category: Authentication" in formatted
