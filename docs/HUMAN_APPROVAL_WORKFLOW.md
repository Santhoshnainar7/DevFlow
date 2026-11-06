# DevFlow Human Approval Workflow Guide

> **Phase**: 04 — Human Approval Workflow  
> **Status**: COMPLETE ✅  
> **Security Baseline**: Server-side permission controls, persistent authorization tracking, cryptographic execution tokens, strict execution gatekeeper.

---

## 1. Overview

The **Human Approval Workflow** is the critical security boundary between bug diagnosis and repository mutation. DevFlow enforces strict, multi-layered authorization to guarantee that **no code is written, no branch is checked out, and no file is modified without explicit, validated human developer approval**.

---

## 2. End-to-End Workflow

```
┌────────────────────────────────────────────────────────┐
│            1. Investigation Completed                  │
│       DevFlow finishes read-only AST diagnosis         │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            2. Publish Proposal to Switch               │
│       Publishes diagnosis, proposed fix, testing plan  │
│       Generates unique approval ID: APP-DF-001-XXXX    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            3. Awaiting Authorized Developer            │
│       Monitors team room for explicit command:         │
│       "APPROVE DF-001" or "REJECT DF-001"              │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            4. Server-Side Validation                   │
│   - Is user in DEVFLOW_APPROVED_USERS?                 │
│   - Is syntax explicit (not conversational)?           │
│   - Is target issue ID matching?                       │
│   - Has proposal expired?                              │
│   - Is this a duplicate approval?                      │
│   - Was the issue cancelled?                           │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
       [ APPROVED ]                [ REJECTED ]
  - Generate single-use        - Mark status REJECTED
    EXEC-DF-001-XXXX token     - Record reason & decider
  - Open modification gate     - Permanent execution block
  - Proceed to Phase 05        - 0 files modified
```

---

## 3. Team Chat Interaction Standard

When an investigation completes, DevFlow posts the exact prompt format:

```text
Investigation completed.

Issue: DF-001
Root cause: Incorrect authentication exception handling.
Affected file: app/routers/auth.py

Proposed fix:
Handle invalid credentials and return HTTP 401.

Testing plan:
- Valid login
- Invalid password
- Missing credentials

Reply with:

APPROVE DF-001
or
REJECT DF-001
```

---

## 4. Security Controls & Architecture

### 4.1 Server-Side Authorization (No Prompt-Only Security)
- Approval validation is enforced by `ApprovalManager` in Python, not by LLM prompting.
- The `DEVFLOW_APPROVED_USERS` configuration allowlist is checked for every command.
- Users not in the allowlist are rejected with an explicit security warning.

### 4.2 Explicit Command Syntax
- Only commands matching `^(APPROVE|REJECT)\s+([A-Za-z0-9_\-]+)$` are processed.
- Conversational or vague responses (e.g. *"sounds good"*, *"looks fine"*, *"yes please"*) are explicitly rejected to prevent accidental authorization.

### 4.3 Single-Use Execution Tokens
- An approved proposal issues a single-use token (`EXEC-{issue_id}-{random}`).
- `CodeModificationGate` consumes the token upon initiating code changes.
- Re-using a consumed token or attempting execution without a token raises `WorkflowStateError` or `UnauthorizedApproverError`.

### 4.4 Persistent Audit Trail
- All approval records (who approved, when, rejection reasons, expiration) are atomically persisted to disk in `data/approvals.json`.
- State survives server restarts and crashes.

### 4.5 Expiration & Cancellation Guards
- Every approval request has an explicit time-to-live (`DEVFLOW_APPROVAL_TIMEOUT_SECONDS`, default 300s).
- Requests past expiration are automatically transitioned to `EXPIRED`.
- Cancelled requests immediately and permanently prohibit approval.

---

## 5. Verified Test Suite (8 Required Test Cases)

| # | Test Scenario | Input / Action | Result | Security Enforcement |
|---|---------------|----------------|:------:|----------------------|
| 1 | **Valid Approval** | `APPROVE DF-001` by `lead_dev` | **PASS** | Validated, execution token issued, write access permitted. |
| 2 | **Invalid Approval** | `MAYBE DF-001`, `sounds good` | **PASS** | Syntax rejected, execution blocked. |
| 3 | **Unauthorized Approval** | `APPROVE DF-001` by `unauthorized_bob` | **PASS** | Rejected: user not in `DEVFLOW_APPROVED_USERS`. |
| 4 | **Rejected Proposal** | `REJECT DF-001` by `lead_dev` | **PASS** | Marked REJECTED, reason logged, execution permanently blocked. |
| 5 | **Duplicate Approval** | Second `APPROVE DF-001` or token re-use | **PASS** | Blocked as duplicate; consumed token cannot re-execute. |
| 6 | **Expired Approval** | `APPROVE DF-002` past expiration TTL | **PASS** | Transitioned to EXPIRED, execution blocked. |
| 7 | **Wrong Issue ID** | `APPROVE DF-999` on active `DF-001` | **PASS** | Mismatch rejected, execution blocked. |
| 8 | **Cancelled Issue** | `APPROVE DF-001` after issue was cancelled | **PASS** | State is CANCELLED, approval rejected. |

