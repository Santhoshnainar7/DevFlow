# DevFlow Bug Investigation Engine Guide

> **Phase**: 03 — Bug Investigation Engine  
> **Status**: COMPLETE ✅  
> **Core Architecture**: Read-only repository inspection, AST symbol analysis, safe reproduction probes, standardized 11-field investigation reporting.

---

## 1. Overview

The **Bug Investigation Engine** enables DevFlow to autonomously analyze software defects reported in team chat rooms without modifying code or hallucinating filenames. It executes an 11-step analysis workflow to inspect actual source files, verify existing test coverage, assess reproduction feasibility, and synthesize root-cause hypotheses with concrete evidence.

---

## 2. The 11-Step Investigation Workflow

```
1. Receive Bug Report
   │
   ▼
2. Extract Description & Title
   │
   ▼
3. Classify Bug Category (8 standard categories)
   │
   ▼
4. Assess Severity & Potential Impact (Critical, High, Medium, Low)
   │
   ▼
5. Inspect Connected Git Repository (Read-only path verification)
   │
   ▼
6. Identify Relevant Source Files (Scored keyword matching)
   │
   ▼
7. Examine Related Functions & Dependencies (Python AST parsing)
   │
   ▼
8. Inspect Existing Tests (Locate existing coverage)
   │
   ▼
9. Safely Attempt Reproduction (Read-only test execution probe)
   │
   ▼
10. Identify Root Cause (Distinguishing confirmed findings from hypotheses)
   │
   ▼
11. Generate Standardized Investigation Report
```

---

## 3. Bug Taxonomy & Classification

The engine classifies all reported issues into one of eight categories:

| Category | Typical Symptoms | Keywords |
|----------|------------------|----------|
| **Authentication** | Login failures, wrong status codes, invalid tokens, 401 unauthorized | `login`, `password`, `token`, `auth`, `401`, `jwt`, `credential` |
| **Validation errors** | Empty inputs, malformed bodies, 422 unprocessable entity | `validation`, `422`, `empty`, `required field`, `pydantic` |
| **API failures** | Unhandled server exceptions, route 404, status 500, payload mismatches | `endpoint`, `status code`, `500`, `404`, `route`, `handler` |
| **Database errors** | Foreign key errors, query timeouts, integrity deadlocks | `database`, `sql`, `query`, `postgres`, `sqlite`, `deadlock` |
| **Frontend issues** | UI misalignment, styling issues, browser rendering | `frontend`, `ui`, `css`, `dom`, `button`, `browser`, `javascript` |
| **Performance problems** | High latency, memory leaks, slow throughput | `slow`, `latency`, `timeout`, `memory leak`, `cpu`, `bottleneck` |
| **Dependency issues** | Missing packages, import errors, version incompatibilities | `import`, `package`, `ModuleNotFoundError`, `pip`, `version` |
| **Unknown** | Ambiguous or non-matching defect descriptions | Default fallback |

---

## 4. Standardized Investigation Report Format

Every investigation produces a structured report following this exact schema:

```text
Issue ID: <e.g. DF-001>
Issue title: <Concise title>
Bug category: <Category>
Severity: <Critical | High | Medium | Low>
Description: <Problem summary>
Affected files: <Inspected files in repository>
Relevant functions: <Inspected functions / symbols>
Root cause: <Confirmed findings vs hypotheses>
Evidence: <Concrete facts from AST and test probes>
Proposed solution: <Targeted fix description>
Testing strategy: <Test command and assertions>
Potential risks: <Side-effects and security implications>
```

---

## 5. Three Reproducible Test Scenarios (Demo Repository)

### Scenario 1: Authentication Failure (Wrong Status Code)
- **Description**: POST `/api/v1/login` returns HTTP 200 with an access token for incorrect password instead of HTTP 401.
- **Classification**: `Authentication` (Severity: `High`).
- **Affected Files**: `app/routers/auth.py`, `app/services/auth_service.py`.
- **Relevant Functions**: `login`, `authenticate_user`.
- **Finding**: In checked-in code, `/api/v1/login` delegates to `authenticate_user` which raises `InvalidPasswordException` (mapped to HTTP 401 in `app/main.py`). The reported 200 indicates either an uncommitted bypass or a deployment version drift.

### Scenario 2: Validation Error (Empty Username Input)
- **Description**: POST `/api/v1/login` with `{"username": "", "password": "..."}` returns 422 Unprocessable Entity.
- **Classification**: `Validation errors` (Severity: `Medium`).
- **Affected Files**: `app/models/schemas.py`, `app/routers/auth.py`.
- **Relevant Functions**: `must_not_be_empty`, `login`.
- **Finding**: `LoginRequest` in `app/models/schemas.py` uses `@field_validator("username", "password")` to reject empty or whitespace-only strings.

### Scenario 3: API Failure / Schema Mismatch (Missing Attribute)
- **Description**: The `/api/v1/login` response payload omits `token_type`, causing client deserialization failures.
- **Classification**: `API failures` (Severity: `High`).
- **Affected Files**: `app/models/schemas.py`, `app/routers/auth.py`.
- **Relevant Functions**: `test_login_response_schema`, `login`.
- **Finding**: Contract requires both `access_token` and `token_type == 'bearer'` in `LoginResponse`.

---

## 6. Security & Execution Rules

1. **Read-Only Code Inspection**: No file writing, checkouts, or git commits are performed during the investigation phase.
2. **Path Traversal Protection**: All file read operations are strictly validated against `DEVFLOW_REPO_PATH`.
3. **No Symbol Hallucination**: Only symbols parsed by the Python `ast` module from real files are reported.
4. **Distinguishing Confirmed vs Hypotheses**: The engine explicitly labels findings as either `CONFIRMED FINDING` (verified by reproduction failure) or `HYPOTHESIS` (inferred from static code analysis).
5. **No Fake Stack Traces**: Test outputs reflect verbatim subprocess execution or explicitly note absence of runtime reproduction.

