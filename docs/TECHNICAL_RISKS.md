# Technical Risks and Mitigations

> **Phase**: 00 — Reconnaissance only.
> **Date**: 2026-11-05

---

## Risk Register

### R01 — Docker Engine Not Running on Windows

| Field | Detail |
|-------|--------|
| **Severity** | 🔴 High |
| **Likelihood** | 🔴 High (confirmed — `docker info` fails) |
| **Impact** | Switch Console cannot start → no local server → no team chat |
| **Detection** | `permission denied while trying to connect to the Docker daemon socket at npipe:////./pipe/docker_engine` |
| **Mitigation** | Start Docker Desktop. If permission denied persists: `net localgroup docker-users %USERNAME% /add` as Administrator, then log out/in. |
| **Fallback** | Use Switch with an external Slack or Discord workspace (agent itself doesn't need Docker — only Switch Console's bundled Mattermost does). |

---

### R02 — Switch Console Windows Installer Not Yet Verified

| Field | Detail |
|-------|--------|
| **Severity** | 🔴 High |
| **Likelihood** | 🟡 Medium |
| **Impact** | Cannot set up team chat integration |
| **Detection** | Download fails or installer errors on launch |
| **Mitigation** | Download directly from `switchagents.ai` or `github.com/sandbox-quantum/switch/releases` at Phase 01 start. Verify installer before proceeding. |
| **Fallback** | Self-host via `docker compose up -d` from the cloned `sandbox-quantum/switch` repo. |

---

### R03 — Switch Agent Token Format Unknown

| Field | Detail |
|-------|--------|
| **Severity** | 🟡 Medium |
| **Likelihood** | 🟡 Medium |
| **Impact** | Agent cannot authenticate to the Switch server; SSE connection refused |
| **Detection** | 401/403 on `GET /v1/agent/events` |
| **Mitigation** | Mount Switch docs MCP server (`https://docs.switchagents.ai/mcp`) immediately after Switch Console install to get the authoritative authentication spec. Log all raw request/response headers during development. |
| **Fallback** | Use Switch Console UI to inspect the token format; check `sandbox-quantum/switch` GitHub README. |

---

### R04 — Gemini API Rate Limits

| Field | Detail |
|-------|--------|
| **Severity** | 🟡 Medium |
| **Likelihood** | 🟢 Low (small-scale hackathon) |
| **Impact** | LLM analysis unavailable; workflow stalls at `ANALYSING` |
| **Detection** | `google.api_core.exceptions.ResourceExhausted` |
| **Mitigation** | Use `gemini-2.5-flash` (highest free-tier quota). Cache results per `room_id`. Implement exponential backoff. |
| **Fallback** | Manual analysis mode: print the diff to chat; developer types the fix directly. |

---

### R05 — Python 3.14 Package Compatibility

| Field | Detail |
|-------|--------|
| **Severity** | 🟡 Medium |
| **Likelihood** | 🟢 Low |
| **Impact** | `pip install` failures; runtime import errors |
| **Detection** | `pip install` error messages citing unsupported Python version |
| **Mitigation** | FastAPI, Uvicorn, Pydantic v2, Pytest, Httpx, google-generativeai all support Python 3.12+. Verify each package at install time. |
| **Fallback** | Install Python 3.12.x in parallel and point the venv to it: `py -3.12 -m venv .venv`. |

---

### R06 — Approval Gate Race Condition

| Field | Detail |
|-------|--------|
| **Severity** | 🟡 Medium |
| **Likelihood** | 🟡 Medium |
| **Impact** | Wrong fix applied; test run triggered without approval |
| **Detection** | Unexpected fix applied; wrong `room_id` state updated |
| **Mitigation** | Key the approval gate on `(room_id, session_id)` tuple. Validate approver against `DEVFLOW_APPROVED_USERS`. Discard approvals after timeout. |
| **Fallback** | For the demo, run only one workflow at a time (single room). |

---

### R07 — Shell Injection via Crafted Bug Report

| Field | Detail |
|-------|--------|
| **Severity** | 🔴 High |
| **Likelihood** | 🟢 Low (if implemented correctly) |
| **Impact** | Arbitrary shell commands executed via `git` subprocess; repo destroyed |
| **Detection** | Unexpected files modified; repo in broken state |
| **Mitigation** | **Always** use `subprocess.run(["git", "log", ...], shell=False)`. Never interpolate message content into command arguments. Maintain an explicit allowlist of permitted git subcommands. Reject any input containing shell metacharacters. |
| **Fallback** | Read-only phase has no write risk. Implementation only runs after verified human approval on a known-good command list. |

---

### R08 — Test Runner Timeout / Infinite Loop

| Field | Detail |
|-------|--------|
| **Severity** | 🟡 Medium |
| **Likelihood** | 🟢 Low |
| **Impact** | DevFlow hangs; Switch room goes silent |
| **Detection** | `subprocess.TimeoutExpired` exception |
| **Mitigation** | Hard-code `timeout=60` in subprocess call. Catch `TimeoutExpired`, kill the process, report timeout to chat. |
| **Fallback** | Configure via `DEVFLOW_TEST_TIMEOUT_SECONDS` env var. |

---

### R09 — Git Repository Has No Initial Commit

| Field | Detail |
|-------|--------|
| **Severity** | 🟡 Medium |
| **Likelihood** | 🔴 High (confirmed — repo is empty) |
| **Impact** | `git log`, `git diff HEAD`, `git show` all fail on empty repo |
| **Detection** | `fatal: your current branch 'master' does not have any commits yet` |
| **Mitigation** | Make initial commit as the very first action of Phase 01. |
| **Action** | Run at start of Phase 01: |

```powershell
git add .
git commit -m "Phase 00: initial documentation and planning"
```

---

### R10 — Hackathon Time Constraint (4 Days)

| Field | Detail |
|-------|--------|
| **Severity** | 🔴 High |
| **Likelihood** | 🔴 High |
| **Impact** | Incomplete implementation; demo fails |
| **Detection** | Missed phase milestones |
| **Mitigation** | Strictly follow phase plan. Build the minimum viable demo first. Use the five sample_app bugs as the controlled demo script. Skip optional features (multi-room concurrency, Redis state, push-to-remote) unless time permits. |

---

## Risk Priority Matrix

| Risk | Severity | Likelihood | Priority |
|------|----------|------------|----------|
| R01 Docker not running | 🔴 High | 🔴 High | **P1 — Fix before Phase 01** |
| R02 Switch installer | 🔴 High | 🟡 Medium | **P1 — Verify before Phase 01** |
| R07 Shell injection | 🔴 High | 🟢 Low | **P1 — Design-time control** |
| R10 Time constraint | 🔴 High | 🔴 High | **P1 — Scope control** |
| R09 Empty git repo | 🟡 Medium | 🔴 High | **P2 — Fix at Phase 01 start** |
| R03 Token format | 🟡 Medium | 🟡 Medium | **P2 — Verify after Switch install** |
| R06 Approval race | 🟡 Medium | 🟡 Medium | **P2 — Single-room demo** |
| R04 Gemini quota | 🟡 Medium | 🟢 Low | **P3 — Backoff + cache** |
| R05 Python 3.14 compat | 🟡 Medium | 🟢 Low | **P3 — Verify at install** |
| R08 Test timeout | 🟡 Medium | 🟢 Low | **P3 — Hard timeout** |

