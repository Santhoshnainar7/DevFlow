# DevFlow Security Model & Safeguards

## 1. Security Philosophy: Defense-in-Depth

Autonomous AI coding agents present severe operational risks if allowed to edit codebases or run commands without oversight. DevFlow implements a **strict, multi-layered defense-in-depth model** where autonomous reasoning is physically decoupled from disk modification by server-side authorization gates.

```text
[ Developer Chat ] 
       │ 
       ▼ 
[ Read-Only Investigation ] ──── (AST Parsing / Read-Only Probes - Zero Writes Allowed)
       │ 
       ▼ 
╔══════════════════════════════════════════════════════════════╗
║                HUMAN-IN-THE-LOOP APPROVAL GATE               ║
║  1. Explicit Command Syntax Check: APPROVE <issue_id>        ║
║  2. Server-Side Allowlist: DEVFLOW_APPROVED_USERS            ║
║  3. Single-Use Cryptographic Execution Token (TTL Expiry)    ║
║  4. Replay & Duplicate Execution Blocker                     ║
╚══════════════════════════════════════════════════════════════╝
       │ 
       ▼ (Token Granted)
[ Controlled Execution Engine ] 
       │ 
       ├── Working Tree Dirty Check (Never overwrite uncommitted dev work)
       ├── Git Branch Isolation (Never touch main/master directly)
       ├── Workspace Boundary Enforcement (No writes outside demo_repository/)
       ├── Controlled Pytest Execution (shell=False, hard timeout guard)
       └── Atomic Auto-Rollback (Instantly revert changes if tests fail)
```

---

## 2. Core Security Controls

### 2.1 Server-Side Approval Gate (Phase 04)
- **Zero Unapproved Writes**: The code modifier (`FixExecutor`) requires a valid, unconsumed execution token issued exclusively by `ApprovalManager.authorize_code_modification()`. No chat message, prompt injection, or automated agent can bypass this requirement.
- **RBAC Allowlist**: Only users explicitly enumerated in `DEVFLOW_APPROVED_USERS` can approve or reject proposals. Unrecognized users receive an HTTP 403 / security block message.
- **Single-Use Cryptographic Tokens**: When approval is granted, a token (`EXEC-<issue_id>-<16_byte_nonce>`) is generated with a strict time-to-live (default: 15 minutes). Once consumed during branch creation, the token is permanently invalidated.
- **Duplicate & Replay Protection**: Attempting to replay an approval command or reuse an exhausted token raises `WorkflowStateError` and blocks duplicate execution.

### 2.2 Workspace & Filesystem Sandboxing (Phase 03 & 05)
- **Directory Traversal Guard**: All file resolution paths are normalized and verified via `Path.resolve().is_relative_to(repo_root)`. Path traversal attempts (e.g. `../../etc/passwd` or `..\Windows\System32`) trigger immediate security errors.
- **Read-Only AST Inspection**: Bug analysis uses Python's standard `ast` module to read syntax trees without executing untrusted Python code or evaluating modules.
- **Target File Boundary**: Code fixes are strictly constrained to files within the designated repository root. Attempts to modify files outside the workspace are rejected.

### 2.3 Git Branch Isolation & Invariants (Phase 05 & 06)
- **Main Branch Protection**: DevFlow is architecturally prohibited from pushing to or modifying `main` or `master`.
- **Isolated Feature Branches**: Every fix is developed on a distinct branch: `devflow/fix-<issue_id>-<timestamp>`.
- **Pre-Flight Cleanliness Check**: Before checking out a branch or modifying files, `GitWorkflow` inspects `git status`. If uncommitted developer changes exist, execution immediately halts to prevent data loss.
- **No Auto-Merge**: Pull requests opened via the GitHub API remain in open review state. DevFlow never automatically merges code into production branches.

### 2.4 Controlled Command Execution (Phase 05)
- **No Shell Execution**: Subprocesses are spawned using list-argument vectors with `shell=False` to prevent shell injection attacks.
- **Timeout Protection**: Test suites run under strict timeout ceilings (default: 30–60s) via `subprocess.run(timeout=...)`. Tests that hang or attempt infinite loops are terminated safely with `ExecutionTimeoutError`.
- **Atomic Rollback**: If a fix fails verification tests, DevFlow immediately triggers `git checkout -- .` to restore the working tree to its clean baseline.

### 2.5 Credential & Token Protection (Phase 06)
- **Token Masking**: GitHub tokens and webhook secrets are masked in logs and representation strings (`ghp_1234...wxyz`). Full tokens are never included in API responses or chat reports.
- **Environment Isolation**: All credentials reside in `.env`, which is included in `.gitignore` and never committed to version control.
- **Graceful Offline Fallback**: In the absence of a configured `GITHUB_TOKEN`, DevFlow seamlessly operates in local mode, ensuring external network failure does not impact local functionality.

---

## 3. Threat Matrix & Mitigations

| Threat | Attack Vector | DevFlow Mitigation |
|---|---|---|
| **Prompt Injection** | Malicious chat message trying to force file write | Server-side validation layer. Regex parser requires exact `APPROVE <id>`, verified against user allowlist. |
| **Unauthorized Approval** | Guest user submits `APPROVE DF-001` | Checked against `DEVFLOW_APPROVED_USERS`. Unauthorized attempts logged and rejected. |
| **Replay Attack** | Resubmitting previously approved token | Tokens are single-use (`_consumed_tokens.add(token)`). Duplicate execution raises `WorkflowStateError`. |
| **Directory Traversal** | Patch targeting `../../etc/shadow` | `GitWorkflow.validate_target_path()` enforces `is_relative_to(repo_root)`. |
| **Denial of Service** | Infinite test loop in reproduction | Hard subprocess timeout ceiling kills runaway processes. |
| **Production Corruption** | Overwriting `main` branch | Invariant check forbids `main` / `master` as target branches. |

