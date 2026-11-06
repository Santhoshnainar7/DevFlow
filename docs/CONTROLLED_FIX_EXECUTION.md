# DevFlow Controlled Code Fixing and Test Execution Guide

> **Phase**: 05 — Controlled Code Fixing and Test Execution  
> **Status**: COMPLETE ✅  
> **Security Baseline**: Isolated branch execution, single-use token consumption, controlled command runner, automated revert on test failure, zero auto-push policy.

---

## 1. Overview

**Phase 05** completes the autonomous loop from approved bug diagnosis to verified code fix. DevFlow guarantees that code changes are confined strictly to isolated fix branches, executed with controlled subprocess commands, validated against automated test suites, and reverted if tests fail.

---

## 2. The 10-Step Controlled Fix Workflow

```
┌────────────────────────────────────────────────────────┐
│            1. Receive Approved Issue                   │
│       Contains FixPlan & single-use execution token    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            2. Validate Approval Again                  │
│       Server-side check: Token valid & unconsumed      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            3. Verify Repository State                  │
│       Checks for uncommitted developer changes         │
│       Aborts if dirty (never overwrites developer work)│
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            4. Create Isolated Working Branch           │
│       Checkout devflow/fix-<issue_id>-<timestamp>      │
│       Main branch is NEVER modified directly           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            5. Apply Proposed Fix                       │
│       Restricted to authorized files in workspace      │
│       Rejects path traversal & unauthorized extensions │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            6. Inspect Resulting Diff                   │
│       Generates and logs unified diff                  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            7. Run Relevant Tests                       │
│       Executes controlled pytest subprocess            │
│       Enforces strict command timeout                  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            8. Run Broader Test Suite                   │
│       Verifies no regressions across repository        │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            9. Analyze Test Failures                    │
│       Extracts exact assertion failure trace           │
│       If tests fail: Auto-revert workflow changes      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│           10. Prepare Execution Report                 │
│       Posts structured report to team room             │
│       Zero auto-commit, zero auto-push, zero merge     │
└────────────────────────────────────────────────────────┘
```

---

## 3. Standard Execution Report Schema

Every execution run produces a structured report matching the required format:

```text
Issue ID: DF-001
Approval ID: APP-DF-001-5AA9FD63
Branch: devflow/fix-df001-1793979920
Files changed: app/services/auth_service.py
Changes made: Applied 1 targeted code patches.
Tests executed: 7
Tests passed: 7
Tests failed: 0
Execution status: SUCCESS
Remaining risks: Fix staged on isolated branch. Ready for code review and manual merge.

--- Code Diff ---
--- a/app/services/auth_service.py
+++ b/app/services/auth_service.py
@@ -25,3 +25,4 @@
     if _USER_STORE[username] != password:
         raise InvalidPasswordException(username)
+    # Verified patch
```

---

## 4. Strict Safety & Security Rules

1. **Main Branch Protection**: Code changes are strictly isolated to `devflow/fix-<issue>-<timestamp>`. The main/master branch is never touched.
2. **Preservation of Developer Work**: If `git status` reveals uncommitted developer changes, the workflow immediately aborts with `FAILED_DIRTY_REPO`.
3. **No Arbitrary Commands**: Test execution is restricted to strictly allowlisted commands (`[sys.executable, "-m", "pytest", ...]`) using `shell=False`.
4. **Workspace Boundary Enforcement**: Patches targeting paths outside the repository or forbidden extensions are rejected with `FAILED_UNAUTHORIZED_FILE`.
5. **Accurate Test Reporting**: Test counts (executed, passed, failed) are parsed verbatim from `pytest` output. Successful results are never fabricated.
6. **Automatic Revert on Failure**: If any test fails, times out, or encounters a missing dependency:
   - Proposed changes are safely reverted to the pre-fix state.
   - The diagnosis is preserved.
   - The report is marked with `requires_human_intervention = True`.
7. **No Auto-Push / No Auto-Merge**: Fixed code remains staged on the local branch for human peer review.

---

## 5. Verification Matrix (All 8 Required Scenarios)

| # | Scenario | Condition / Action | Result | Security & Safety Outcome |
|---|----------|--------------------|:------:|---------------------------|
| 1 | **Approved Bug Fix** | Valid approval token, clean repo | **PASS** | Isolated branch created, patch applied, diff verified. |
| 2 | **Fix That Passes Tests** | Patch satisfies all assertions | **PASS** | Status `SUCCESS`, 7/7 tests passed, staged locally. |
| 3 | **Fix That Fails Tests** | Patch causes assertion error | **PASS** | Status `FAILED_TESTS`, changes safely reverted, human help requested. |
| 4 | **Existing Unrelated Changes** | Working tree has dirty uncommitted edits | **PASS** | Status `FAILED_DIRTY_REPO`, aborts before touching any files. |
| 5 | **Missing Test Dependencies** | Test triggers `ModuleNotFoundError` | **PASS** | Status `FAILED_DEPENDENCY`, changes reverted, dependency flagged. |
| 6 | **Test Timeout** | Slow test exceeds timeout threshold | **PASS** | Status `FAILED_TIMEOUT`, subprocess killed, changes reverted. |
| 7 | **Invalid Approval** | Unapproved, expired, or forged token | **PASS** | Status `FAILED_INVALID_APPROVAL`, blocked by gatekeeper. |
| 8 | **Unauthorized File Modification**| Patch targets `../../outside.py` or `.exe` | **PASS** | Status `FAILED_UNAUTHORIZED_FILE`, write rejected. |

