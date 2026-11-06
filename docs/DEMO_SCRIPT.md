# DevFlow 3-Minute Hackathon Demonstration Script

This script outlines the video demonstration for DevFlow, tailored to the SandboxAQ "Flip the Switch" Hackathon judging criteria.

---

## Demonstration Overview
- **Total Duration**: 3 minutes (180 seconds)
- **Primary Channels**: Switch Console / Discord `#bug-reports`
- **Target Repository**: `demo_repository/` (FastAPI authentication service)
- **Defect Demonstrated**: Issue `DF-001` (Authentication 500 error instead of HTTP 401 on invalid password)

---

## Timeline & Narration

### [0:00 – 0:30] Problem Statement & Value Proposition
* **Visual**: Camera / slide of engineering context-switching graph. Transition to Discord / Switch interface.
* **Speaker**:
  > *"Modern engineering teams spend over 30% of their sprints reproducing bug reports, sifting through stack traces, and switching contexts between chat rooms and IDEs. Autonomous coding agents could help, but until now they've lacked safety guardrails—either running unchecked with arbitrary write permissions or hallucinating fake fixes.
  >
  > Today we introduce **DevFlow**: an autonomous, human-in-the-loop bug investigation and fix agent connected directly to our team chat via Switch. DevFlow investigates real codebases, isolates reproduction test cases, enforces strict human approval gates, and verifies all fixes on isolated git branches before opening pull requests."*

---

### [0:30 – 0:55] Bug Report in Team Chat (Switch & Discord)
* **Visual**: Switch Console and Discord `#bug-reports` channel side by side.
* **Action**: Developer types into `#bug-reports`:
  `@devflow Bug: The /auth/login endpoint crashes with HTTP 500 Internal Server Error when an invalid password is provided.`
* **Speaker**:
  > *"A developer reports an authentication defect directly in the team's `#bug-reports` channel. Notice that DevFlow is immediately awakened by Switch's message gateway. It acknowledges the report, creates tracking ID `DF-001`, and initiates an automated, read-only investigation."*
* **On-Screen Chat Output**:
  ```text
  devflow: Bug report received [DF-001]: The /auth/login endpoint crashes with HTTP 500... Initial triage queued.
  devflow: Investigating [DF-001]: Inspecting source files and test suites in demo_repository...
  ```

---

### [0:55 – 1:25] Autonomous Codebase Investigation
* **Visual**: Split screen showing DevFlow terminal logs and the resulting diagnostic card in chat.
* **Speaker**:
  > *"Under the hood, DevFlow’s Bug Investigation Engine parses our repository using Python AST. It inspects actual source files—`auth.py`, `auth_service.py`, and `test_auth.py`—without modifying a single byte on disk. It runs a read-only reproduction probe, capturing real pytest exit codes and stack traces.
  >
  > Notice the structured 11-field diagnostic report DevFlow posts to the channel. It clearly distinguishes confirmed facts from hypotheses. It confirms that `authenticate_user` raises an unhandled `AuthenticationError`, causing FastAPI to return HTTP 500 instead of a clean 401 Unauthorized."*
* **On-Screen Chat Output**:
  ```text
  Issue ID: DF-001
  Issue title: Auth failure returns 500 instead of 401
  Bug category: Authentication
  Severity: High
  Description: Invalid credentials trigger uncaught 500
  Affected files: app/routers/auth.py, app/services/auth_service.py
  Relevant functions: login_for_access_token, authenticate_user
  Root cause: CONFIRMED: authenticate_user raises unhandled AuthenticationError
  Evidence: Observed test failure in tests/test_auth.py with status 500
  Proposed solution: Catch AuthenticationError in login endpoint and raise HTTPException(401)
  Testing strategy: Run test_auth_invalid_credentials expecting HTTP 401
  Potential risks: Ensure valid user login tokens are unaffected
  ```

---

### [1:25 – 1:50] The Human Approval Checkpoint
* **Visual**: Zoom in on the approval prompt in Switch/Discord.
* **Speaker**:
  > *"Here is DevFlow's critical safety boundary: **Zero file modifications may occur without server-side approval validation.**
  >
  > DevFlow generates unique approval request `APP-DF-001-A1B2C3` with a 15-minute expiration window. If an unauthorized guest attempts to approve, DevFlow rejects them. Only authorized developers listed in `DEVFLOW_APPROVED_USERS` can authorize code modifications."*
* **Action**: Authorized developer replies:
  `APPROVE DF-001`
* **On-Screen Chat Output**:
  ```text
  devflow: Fix APPROVED for [DF-001] by @lead_dev. Execution gate opened. Single-use token issued.
  ```

---

### [1:50 – 2:30] Controlled Code Fixing & Automated Test Execution
* **Visual**: Show Git branch graph and terminal running tests.
* **Speaker**:
  > *"Once approved, DevFlow verifies that the working directory has no uncommitted changes. It never touches `main` directly. Instead, it checkouts an isolated branch: `devflow/fix-df-001-20261106`.
  >
  > It applies the approved patch to `app/routers/auth.py` and immediately triggers automated `pytest` execution under a subprocess timeout guard.
  >
  > Look at the test output: all 7 test cases pass, including the previously failing `test_auth_invalid_credentials`! If tests had failed, DevFlow would have automatically rolled back the working tree and alerted human engineers."*
* **On-Screen Chat Output**:
  ```text
  Fix implementation started for [DF-001] on isolated branch `devflow/fix-df-001-20261106`. Modifying app/routers/auth.py.
  Tests COMPLETED for [DF-001]: 7/7 passed on branch `devflow/fix-df-001-20261106`.
  ```

---

### [2:30 – 3:00] Final Engineering Report & Impact
* **Visual**: Final engineering report posted in Switch / Discord and GitHub Pull Request page.
* **Speaker**:
  > *"With verification complete, DevFlow publishes a comprehensive final engineering report containing the exact problem summary, root cause, test counts, unified git diff, and a GitHub Pull Request prepared for human peer review.
  >
  > Notice what we achieved: within 3 minutes, an authentication bug reported in team chat was diagnosed, approved by an engineer, patched on an isolated branch, tested with 100% pass rate, and prepared for review—with zero context switching, zero hallucinatory code, and absolute human control.
  >
  > That is autonomous coding done right. That is DevFlow."*
* **On-Screen Chat Output**:
  ```text
  Final Engineering Report [DF-001]:
  Issue identifier: DF-001
  Problem description: Invalid credentials result in uncaught internal server error.
  Root cause: CONFIRMED: authenticate_user raises unhandled AuthenticationError
  Implemented solution: Added HTTPException(401) on AuthenticationError.
  Files changed: app/routers/auth.py
  Git branch: devflow/fix-df-001-20261106
  Tests executed: 7
  Actual test results: 7 passed, 0 failed (SUCCESS)
  GitHub references: PR #42 (https://github.com/org/repo/pull/42)
  ```

