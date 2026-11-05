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

## Phase 02 — DevFlow Agent Core (~6 hours)

**Goal**: Build the DevFlow Python agent with SSE listener, 10-state workflow, and Gemini integration. Test locally without Switch.

```
devflow/
├── agent.py           # Starts SSE listener loop; dispatches to workflow
├── workflow.py        # 10-state machine
├── git_reader.py      # Read-only git subprocess wrappers (allowlist enforced)
├── llm_client.py      # Gemini API calls (google-generativeai)
├── approval_gate.py   # Per-room approval tracking + timeout
├── test_runner.py     # pytest subprocess (shell=False, timeout=60)
├── switch_client.py   # HTTP POST to Switch rooms
└── config.py          # Pydantic settings from .env
```

Local test without Switch (simulate a Switch event via curl):
```powershell
# Start agent
python -m devflow.agent

# In another terminal — simulate incoming Switch SSE event
# (agent logs should show acknowledgement and investigation steps)
```

---

## Phase 03 — Switch Integration (~4 hours)

**Goal**: Connect DevFlow to Switch Console. Verify message delivery end-to-end through Mattermost.

1. Install Switch Console from `switchagents.ai`.
2. Launch — Docker containers start automatically.
3. Open bundled Mattermost in browser.
4. Register DevFlow: name=`devflow`, SSE events endpoint from Switch Console.
5. Test: type `@devflow hello` in Mattermost → agent acknowledges.

---

## Phase 04 — Full Workflow End-to-End (~3 hours)

**Goal**: Wire up the approval gate and test runner. Run Bug 01 through the complete 10-step workflow.

1. Post bug report in Mattermost.
2. DevFlow investigates → posts proposed fix.
3. Developer replies `yes`.
4. DevFlow applies fix → runs pytest → reports results.

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

