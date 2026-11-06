# DevFlow — Implementation Plan (All Phases)

> **Phase 00**: Documentation only. No code exists yet.
> **Last Updated**: 2026-11-05
> **Hackathon**: Flip the Switch | Duration: 4 days

---

## Project Summary

DevFlow is a Switch-connected autonomous agent that receives bug reports in team chat, investigates a local Git repository using Gemini AI, proposes fixes with explicit human approval, runs automated tests, and reports results — all within the team chat interface.

---

## Phase Overview

| Phase | Name | Goal | Status |
|-------|------|------|--------|
| **00** | Reconnaissance | Environment setup, research, planning | ✅ Complete |
| **01** | Project Foundation & Demo App | Modular backend foundation, health checks, tests & demo repo | ✅ Complete |
| **02** | DevFlow Agent Core | SSE listener + workflow state machine + Gemini integration | ⏳ Pending Approval |
| **03** | Switch Integration | Connect DevFlow to Switch Console + Mattermost | ⏳ Planned |
| **04** | Approval Gate + Test Runner | Full workflow end-to-end | ⏳ Planned |
| **05** | Bug Demonstrations | Inject each bug; run DevFlow end-to-end | ⏳ Planned |
| **06** | Polish + Documentation | README, demo script, error handling | ⏳ Planned |
| **Total** | | | **~21 hours / 4 days** |

---

## Phase 00 — Reconnaissance ✅ COMPLETE

### Deliverables
- [x] `docs/ENVIRONMENT_SETUP.md`
- [x] `docs/RESEARCH.md`
- [x] `docs/ARCHITECTURE.md`
- [x] `docs/TECHNICAL_RISKS.md`
- [x] `docs/IMPLEMENTATION_PLAN.md` (this file)

---

## Phase 01 — Project Foundation & Demo Repository ✅ COMPLETE

### Deliverables & Accomplished Tasks
- [x] **Project Structure**: Established modular layout with `backend/app/{core,services,models,integrations,workflows}`, `demo_repository/`, `tests/`, `scripts/`, `docs/`.
- [x] **Git Initialization & Commit**: Initial commit established on `master` branch.
- [x] **Python Virtual Environment**: Python 3.14 virtual environment configured in `.venv/`.
- [x] **Dependency Management**: Configured production (`requirements.txt`) and development (`requirements-dev.txt`) dependencies.
- [x] **Configuration Validation (`backend/app/core/config.py`)**: Type-safe settings loaded from `.env` and environment variables with strict port, timeout, log-level, and approved-users validation using Pydantic.
- [x] **Structured Logging (`backend/app/core/logging.py`)**: Built JSON and readable structured formatters supporting contextual metadata (`room_id`, `step`, timestamps, levels).
- [x] **Centralized Exception Handling (`backend/app/core/exceptions.py`)**: Domain exceptions (`UnauthorizedApproverError`, `WorkflowStateError`, `ExecutionTimeoutError`, `RepositoryError`) mapped to standardized JSON responses across FastAPI.
- [x] **Health Check & Service API (`backend/app/main.py`)**: Created `GET /health` and `GET /` endpoints with latency tracking and logging middleware.
- [x] **Demo Target Repository (`demo_repository/`)**: Scaffolded minimal FastAPI login application with in-memory auth service, custom exception handlers, and 7 automated Pytest test cases verifying the green baseline.
- [x] **Automated Test Suite (`tests/`)**: Implemented unit and integration tests for configuration validation, logging formatters, centralized exception handlers, and health endpoints.
- [x] **Developer Scripts & Documentation**: Created `scripts/run_dev.py` and comprehensive `README.md`.

### 1.1 Pre-Phase Setup Commands
```powershell
# 1. Make initial commit (fix R09)
cd C:\Users\santh\DevFlow
git add docs\
git commit -m "Phase 00: reconnaissance and planning documentation"

# 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install sample app dependencies
pip install fastapi uvicorn pydantic
pip install pytest httpx pytest-asyncio
```

### 1.2 Proposed Project Structure
```
C:\Users\santh\DevFlow\
└── sample_app\
    ├── app\
    │   ├── __init__.py
    │   ├── main.py                   # FastAPI app instance; mounts router; registers exception handlers
    │   ├── routers\
    │   │   ├── __init__.py
    │   │   └── auth.py               # POST /api/v1/login endpoint
    │   ├── models\
    │   │   ├── __init__.py
    │   │   └── schemas.py            # LoginRequest, LoginResponse, ErrorResponse (Pydantic)
    │   ├── services\
    │   │   ├── __init__.py
    │   │   └── auth_service.py       # authenticate_user(); in-memory user store
    │   └── core\
    │       ├── __init__.py
    │       └── exceptions.py         # Custom exception classes + FastAPI handlers
    └── tests\
        ├── __init__.py
        ├── conftest.py               # TestClient fixture; mock user store
        └── test_auth.py              # 7 test cases
```

### 1.3 Component Responsibilities

#### `app/main.py`
- Creates the `FastAPI()` application instance.
- Registers the `auth` router under the `/api/v1` prefix.
- Registers global exception handlers for all three custom exceptions.

#### `app/routers/auth.py` — Login Endpoint

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/login` | Accepts `LoginRequest`, returns `LoginResponse` or raises custom exception |

#### `app/models/schemas.py` — Pydantic Schemas

| Schema | Fields | Purpose |
|--------|--------|---------|
| `LoginRequest` | `username: str`, `password: str` | Validates non-empty credential input |
| `LoginResponse` | `access_token: str`, `token_type: str` | Wraps successful login token |
| `ErrorResponse` | `detail: str` | Standardised error body |

#### `app/services/auth_service.py` — Business Logic
- Maintains a **small in-memory user dict** (no database dependency).
- `authenticate_user(username, password)` — looks up user; compares password (plain-text; hashing intentionally omitted to keep demo focused on logic bugs).
- Returns the user record on success, or raises the appropriate custom exception.

#### `app/core/exceptions.py` — Error Handling

| Exception Class | Trigger | HTTP Status |
|-----------------|---------|-------------|
| `UserNotFoundException` | Username not found in store | `404 Not Found` |
| `InvalidPasswordException` | Username found, password wrong | `401 Unauthorized` |
| `MissingCredentialsException` | Empty username or password | `422 Unprocessable Entity` |

Global exception handlers convert each into a structured `ErrorResponse` JSON body.

### 1.4 Test Cases (Green Baseline — 7 Tests)

| Test ID | Scenario | Input | Expected Status | Expected Body |
|---------|----------|-------|-----------------|---------------|
| `test_login_success` | Valid credentials | Correct username + password | `200 OK` | `access_token` present |
| `test_login_wrong_password` | Wrong password | Correct username, wrong password | `401 Unauthorized` | `detail` message |
| `test_login_unknown_user` | Unknown username | Non-existent username | `404 Not Found` | `detail` message |
| `test_login_empty_username` | Missing username | Empty string username | `422 Unprocessable Entity` | validation error |
| `test_login_empty_password` | Missing password | Empty string password | `422 Unprocessable Entity` | validation error |
| `test_login_missing_body` | No request body | No JSON payload | `422 Unprocessable Entity` | validation error |
| `test_login_response_schema` | Schema conformance | Valid credentials | `200 OK` | Both `access_token` and `token_type` present |

### 1.5 HTTP Status Code Map

| Condition | Status |
|-----------|--------|
| Successful login | `200 OK` |
| Malformed / missing body | `422 Unprocessable Entity` |
| User not found | `404 Not Found` |
| Incorrect password | `401 Unauthorized` |
| Unexpected server error | `500 Internal Server Error` |

### 1.6 Verification
```powershell
cd C:\Users\santh\DevFlow
pytest sample_app\tests\ -v
# Expected: 7 passed
```

### 1.7 Planned Bug Injection Scenarios (DevFlow Demos)

These are introduced **one at a time**, after the green baseline is confirmed. Each represents a Phase 05 demo run.

| Bug # | Location | Injection | Symptom | DevFlow Signal |
|-------|----------|-----------|---------|----------------|
| Bug 01 | `auth.py` | Return `200` instead of `401` for wrong password | `test_login_wrong_password` fails | Test status code assertion |
| Bug 02 | `auth_service.py` | Raise `UserNotFoundException` on password mismatch instead of `InvalidPasswordException` | Wrong status (404 instead of 401) | Mismatched exception class in traceback |
| Bug 03 | `schemas.py` | Remove `token_type` from `LoginResponse` | `test_login_response_schema` fails | Schema validation / `KeyError` |
| Bug 04 | `auth_service.py` | Flip equality check (`!=` instead of `==`) | `test_login_success` fails (401), `test_login_wrong_password` passes incorrectly | Inversely correlated test failures |
| Bug 05 | `main.py` | Remove exception handler for `InvalidPasswordException` | `500` instead of `401` for wrong password | Test sees 500; unhandled exception in logs |

### 1.8 End of Phase 01 — Git Commit
```powershell
git add sample_app\
git commit -m "Phase 01: sample FastAPI login app — green test baseline (7/7)"
```

---

## Phase 02 — SWITCH AND CODING AGENT INTEGRATION (Status: COMPLETE ✅)

**Goal**: Connect DevFlow to the actual Switch collaboration environment and verify bidirectional communication in `#bug-reports`.

- [x] **Switch Local Environment**: Switch Console v0.31.0 active, local coordination server running at `http://127.0.0.1:52774`.
- [x] **Supported Coding Agent**: Codex agent configured for `devflow` working in `C:\Users\santh\DevFlow`.
- [x] **Team Engineering Room**: Public Mattermost room `#bug-reports` created with developer, `switch-buddy`, and `devflow`.
- [x] **Agent Identity & System Instructions**: Triage instructions configured with auto mode on, bypass off, and strict read-only repository inspection.
- [x] **Environment Configuration**: Updated `.env` with `SWITCH_AGENT_TOKEN`, `SWITCH_SERVER_URL`, and `SWITCH_AGENT_ID`.
- [x] **Documentation**: Created `docs/SWITCH_SETUP.md` capturing architecture, settings, and triage instructions.
- [x] **Verification**: All test cases verified in `#bug-reports`:
  - Normal message received and answered.
  - Complete bug report received, `DF-001` assigned, read-only code inspection performed, no files modified.
  - Missing field questions prompted when necessary.
  - Second separate bug report triaged with unique tracking.
  - Verified `demo_repository/` has zero modifications (`git status` clean).

---

## Phase 03 — BUG INVESTIGATION ENGINE (Status: COMPLETE ✅)

**Goal**: Enable DevFlow to investigate real software bugs using the connected Git repository with read-only inspection, reproduction probing, and structured report generation.

- [x] **Investigation Domain Models (`backend/app/models/investigation.py`)**: Defined `BugCategory` enum (8 categories), `Severity` enum, `FileInspection`, `ReproductionResult`, `InvestigationRequest`, and `InvestigationReport` with `.to_formatted_report()`.
- [x] **Bug Classifier & Severity Assessment (`backend/app/services/bug_classifier.py`)**: Heuristic classification across Authentication, Validation errors, API failures, Database errors, Frontend issues, Performance problems, Dependency issues, and Unknown.
- [x] **Safe Repository Inspector (`backend/app/services/repository_inspector.py`)**: Read-only AST symbol extraction (real functions/classes, no hallucinated symbols), path traversal protection, keyword search scoring, and existing test discovery.
- [x] **Safe Reproduction Runner (`backend/app/services/reproduction_runner.py`)**: Read-only test execution probe, timeout guard, zero source file changes, and accurate reproduction reporting.
- [x] **Investigation Engine Orchestrator (`backend/app/services/investigation_engine.py`)**: Implements the full 11-step workflow, distinguishing confirmed findings from hypotheses.
- [x] **State Machine Workflow (`backend/app/workflows/triage.py`)**: Managed state transitions (IDLE -> RECEIVED -> CLASSIFYING -> INSPECTING_REPO -> REPORT_GENERATED).
- [x] **Backend API Endpoints (`backend/app/main.py`)**: Exposed `POST /api/v1/investigate` and `POST /api/v1/investigate/formatted`.
- [x] **Switch Integration Instructions (`AGENTS.md`)**: Configured workspace-level system instructions matching Phase 03 requirements.
- [x] **Three Reproducible Bug Scenarios**:
  - Scenario 1: Authentication failure (wrong password returns 200).
  - Scenario 2: Validation error (empty username parameter).
  - Scenario 3: API failure / Contract mismatch (missing response token_type attribute).
- [x] **Automated Test Suite (`tests/test_investigation.py`)**: 12/12 automated tests verifying classification, AST inspection, security boundaries, scenario investigations, and thread safety.
- [x] **Documentation**: Created `docs/BUG_INVESTIGATION_ENGINE.md`.

---

## Phase 04 — HUMAN APPROVAL WORKFLOW (Status: COMPLETE ✅)

**Goal**: Create a reliable, server-side human approval mechanism between bug investigation and code modification.

- [x] **Approval Data Models (`backend/app/models/approval.py`)**: `ApprovalDecision`, `ApprovalRequest` with `.to_switch_prompt()`, `ApprovalActionPayload`, and `ApprovalValidationResult`.
- [x] **Persistent Approval Service (`backend/app/services/approval_manager.py`)**: Atomic JSON persistence (`data/approvals.json`), thread-safe concurrency, allowlist authorization (`DEVFLOW_APPROVED_USERS`), and single-use execution tokens.
- [x] **Code Modification Gatekeeper (`backend/app/services/modification_gate.py`)**: Enforces that zero files or branches can be modified without a verified, unconsumed execution token.
- [x] **Triage Workflow Integration (`backend/app/workflows/triage.py`)**: Integrated `publish_for_approval` and `process_approval` with workflow state transitions (`AWAITING_APPROVAL`, `APPROVED`, `REJECTED`).
- [x] **Backend API Endpoints (`backend/app/main.py`)**: Exposed `POST /api/v1/approvals/decide` and `GET /api/v1/approvals/{issue_id}`.
- [x] **Agent System Instructions (`AGENTS.md`)**: Documented Phase 04 instructions for Switch team rooms.
- [x] **All 8 Required Test Cases Verified (`tests/test_approval.py`)**:
  - Valid approval (authorized user, explicit command -> execution token granted)
  - Invalid approval (conversational / ambiguous syntax rejected)
  - Unauthorized approval (users not in allowlist rejected)
  - Rejected proposal (marked REJECTED, execution blocked)
  - Duplicate approval (already-approved proposals and consumed tokens blocked)
  - Expired approval (proposals past TTL rejected)
  - Wrong issue ID (issue mismatch rejected)
  - Approval after cancellation (cancelled issues blocked)
- [x] **Documentation**: Created `docs/HUMAN_APPROVAL_WORKFLOW.md`.

---

## Phase 05 — Bug Demonstrations (~3 hours)

**Goal**: Run all five bug scenarios through DevFlow. Document results.

Each bug cycle:
1. Inject bug (manual edit to sample_app).
2. Confirm tests fail (`pytest` locally).
3. Post bug report to Mattermost.
4. DevFlow: investigate → propose → approve → fix → test → report.
5. Confirm tests pass (7/7).
6. Screenshot the Mattermost conversation for the demo.

---

## Phase 06 — Polish and Documentation (~2 hours)

- Write `README.md` with setup instructions and demo script.
- Record a demo video or screenshots.
- Confirm `.env` is in `.gitignore`.
- Final commit on `main`/`master`.
- Review all security controls against the checklist in `ARCHITECTURE.md`.

---

## Critical Path

```
[Fix Docker] ──→ [Phase 01: Sample App] ──→ [Phase 02: DevFlow Core]
                                        ──→ [Phase 03: Switch Connect]
                                        ──→ [Phase 04: Full Workflow]
                                        ──→ [Phase 05: 5 Bug Demos]
                                        ──→ [Phase 06: Polish]
```

**The Docker fix is the first blocker.** Nothing downstream works without it.

---

## 4-Day Schedule

| Day | Phases | End-of-Day Deliverable |
|-----|--------|------------------------|
| **Day 1** | Fix Docker → Phase 01 → Phase 02 (SSE + Gemini) | DevFlow responds to test input; sample app 7/7 green |
| **Day 2** | Phase 02 (workflow states) → Phase 03 (Switch) | DevFlow lives in Mattermost |
| **Day 3** | Phase 04 (approval + test runner) → Phase 05 (Bug 01–03) | First 3 bugs fixed by DevFlow |
| **Day 4** | Phase 05 (Bug 04–05) → Phase 06 (polish) | Full demo ready |

