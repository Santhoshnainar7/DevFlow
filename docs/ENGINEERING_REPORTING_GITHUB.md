# Phase 06: Engineering Reporting & GitHub Integration

## 1. Overview
DevFlow bridges autonomous AI bug investigation and controlled remediation with team communication platforms (Switch and Discord) and external version control systems (GitHub). Phase 06 delivers:
1. **Switch Lifecycle Updates**: Real-time notifications across 8 operational stages.
2. **Standardized Final Engineering Reports**: Concise summaries with diffs and test results.
3. **GitHub Integration & Safety Guardrails**: Automated issue and pull request creation with strict human-in-the-loop controls.

---

## 2. Part A — Switch Lifecycle Updates (8 Stages)

DevFlow notifies team chat at each stage of the bug fix cycle:

| Stage | Trigger | Content |
|---|---|---|
| **1. Bug Received** | Developer reports bug in chat | Acknowledges receipt, assigns issue ID (`DF-xxx`), and queues triage. |
| **2. Investigation Started** | Read-only analysis begins | Announces AST inspection and test execution against target repository. |
| **3. Investigation Completed** | Diagnosis determined | Publishes structured 11-field diagnostic report with root cause and evidence. |
| **4. Approval Requested** | Fix proposal ready | Prompts human developer with unique approval request (`APP-*`) and syntax instructions. |
| **5. Approval Decided** | Human developer approves/rejects | Validates authorization and command, then announces decision. |
| **6. Fix Started** | Token validated | Announces branch checkout (`devflow/fix-*`) and files to be patched. |
| **7. Tests Completed** | Pytest execution finishes | Reports pass/fail counts and test suite outcome. |
| **8. Final Report Published** | Workflow concludes | Publishes complete engineering summary including diff and links. |

---

## 3. Part B — GitHub Integration & Guardrails

### 3.1 Capabilities
- **Issues**: Creates tracking issues with problem description, root cause diagnosis, and a link back to the Switch room.
- **Pull Requests**: Prepares review-ready pull requests on isolated branches (`devflow/fix-*`) targeting `main`.

### 3.2 Security Invariants
- **Never Push to Main**: All code changes are restricted to isolated branches. Head branches named `main` or `master` are strictly rejected by `GitHubService.create_pull_request`.
- **Never Auto-Merge**: Pull requests are left open for human code review.
- **Human Approval Gate**: External GitHub mutations require explicit human approval (`is_approved=True`).
- **Token Masking**: Secrets and GitHub tokens are masked in logs and representation strings (`ghp_abc...xyz`).
- **Graceful Offline Fallback**: If `GITHUB_TOKEN` is unset or empty, DevFlow degrades gracefully to local operation with status `"unconfigured"`.

---

## 4. Part C — Final Engineering Report Format

```text
Issue identifier: <Issue ID>
Problem description: <Description>
Root cause: <Confirmed findings vs hypotheses>
Proposed solution: <Proposed solution>
Implemented solution: <Applied changes>
Files changed: <Files>
Tests executed: <Count>
Actual test results: <Passed> passed, <Failed> failed (<Status>)
Git branch: <Branch>
Remaining risks: <Risks>
GitHub references: <Issue URL, PR URL or Offline fallback>

--- Code Diff ---
<Unified Diff>
```

---

## 5. Verification & Test Coverage
The Phase 06 test suite in `tests/test_reporting.py` validates all 16 criteria:
- All 8 lifecycle notifications formatted and dispatched chronologically.
- Rejection and test failure messaging.
- Engineering report synthesis with all Part C fields.
- Offline fallback when GitHub token is unconfigured.
- Human approval requirement for external GitHub actions.
- Rejection of `main`/`master` as head branch.
- Mocked GitHub API responses (HTTP 201 Created for issue and PR).
- Full end-to-end workflow reporting integration in `TriageWorkflow`.

