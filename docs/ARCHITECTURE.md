# DevFlow — System Architecture

> **Phase**: 00 — Design only. No implementation.
> **Date**: 2026-11-05
> **Goal**: Simplest technically valid architecture for a four-day hackathon.

---

## 1. What DevFlow Does

DevFlow is a **Switch-connected autonomous bug investigation and fix agent** that performs this exact workflow:

1. Receive a bug report in a Switch-connected team chat room.
2. Acknowledge the report immediately.
3. Inspect the connected local Git repository (read-only).
4. Identify affected files.
5. Investigate the root cause using Gemini.
6. Prepare a proposed fix.
7. Post the proposal to chat and **wait for explicit human approval**.
8. Implement **only** approved fixes, on a dedicated branch.
9. Run automated tests.
10. Report actual test results back to chat.

---

## 2. Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                    TEAM CHAT (Mattermost)                         │
│  Human: "@devflow  login returns 200 for wrong passwords"         │
│  Human: "yes"  ← approval                                        │
│  DevFlow: "7/7 tests passed. Fix on branch devflow/fix-20261105." │
└──────────────────────────┬────────────────────────────────────────┘
                           │  Switch routes via SSE event stream
                           ▼
┌───────────────────────────────────────────────────────────────────┐
│          SWITCH LOCAL SERVER  (Docker containers)                 │
│          Bundled Mattermost + Switch coordination layer           │
└──────────────────────────┬────────────────────────────────────────┘
                           │  GET /v1/agent/events  (SSE)
                           │  POST /v1/rooms/{id}/messages  (HTTP)
                           ▼
┌───────────────────────────────────────────────────────────────────┐
│               DEVFLOW AGENT  (FastAPI + Python)                   │
│                                                                   │
│  ┌─────────────────┐   ┌────────────────┐   ┌─────────────────┐  │
│  │  SSE Listener   │   │  Workflow       │   │  Approval Gate  │  │
│  │  (httpx + SSE)  │──▶│  State Machine  │──▶│  (blocks until  │  │
│  │                 │   │  (10 states)    │   │   human says    │  │
│  └─────────────────┘   └───────┬────────┘   │   yes / no)     │  │
│                                │            └─────────────────┘  │
│  ┌────────────────┐    ┌───────▼────────┐   ┌─────────────────┐  │
│  │  Git Reader    │    │  Gemini LLM    │   │  Test Runner    │  │
│  │  (read-only    │◀───│  (google-      │   │  (pytest        │  │
│  │   subprocess)  │    │  generativeai) │   │   subprocess,   │  │
│  └────────────────┘    └────────────────┘   │   60s timeout)  │  │
│                                             └─────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
                           │  read / write (approved only, fix branch)
                           ▼
┌───────────────────────────────────────────────────────────────────┐
│          GIT REPOSITORY  (C:\Users\santh\DevFlow\sample_app)      │
└───────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Descriptions

### 3.1 SSE Listener

- Runs as a **background async task** using `httpx` with SSE support.
- Connects to `GET /v1/agent/events` on the Switch local server.
- Authenticates via `Authorization: Bearer <SWITCH_AGENT_TOKEN>`.
- Parses incoming `message.posted` events.
- Filters: only process messages where `author_type == "human"` and body contains `@devflow`.
- Dispatches the message payload to the Workflow Engine.

### 3.2 Workflow State Machine

The core orchestrator. A linear state machine with these states:

| State | Description |
|-------|-------------|
| `IDLE` | Waiting for a message |
| `ACKNOWLEDGED` | Sent acknowledgement to chat |
| `INVESTIGATING` | Running read-only Git inspection |
| `ANALYSING` | Sending context to Gemini LLM |
| `PROPOSING` | Posting proposed fix to chat |
| `AWAITING_APPROVAL` | Blocked; waiting for `yes`/`no` reply |
| `IMPLEMENTING` | Writing the approved fix on a fix branch |
| `TESTING` | Running `pytest` subprocess |
| `REPORTING` | Posting test results to chat |
| `COMPLETE` | Workflow finished |
| `CANCELLED` | Rejected or timed out |

State is keyed by `room_id`. Only one active workflow per room at a time.

### 3.3 Git Reader (Read-Only Investigation)

- Calls the Git CLI via `subprocess.run()` with **list arguments only** (`shell=False`).
- Strictly allowlisted commands:
  - `git log --oneline -n 20`
  - `git status`
  - `git show <filepath>`
  - `git diff HEAD`
  - File reads via Python `open(path, 'r')`.
- **No write operations during investigation**: no `git commit`, no `git checkout`, no file writes.
- During implementation: writes confined to the fix branch only, after verified human approval.

### 3.4 Gemini LLM Client

- Uses `google-generativeai` Python SDK.
- Model: `gemini-2.5-flash` (highest free-tier quota; fast).
- API key: `GEMINI_API_KEY` environment variable.
- Responsibilities:
  - Analyse git diff, file content, error messages.
  - Identify root cause.
  - Draft a minimal, targeted code fix.
  - Write a plain-English explanation for the developer.
- Gemini **does not execute code** — it only produces text proposals.

### 3.5 Approval Gate

- After posting a fix proposal, state → `AWAITING_APPROVAL`.
- Monitors the same `room_id` for a follow-up message.
- **Only messages from authorized users** (configured in `DEVFLOW_APPROVED_USERS`) are accepted.
- Recognized commands: `yes`, `approve`, `no`, `reject`, `cancel`.
- Auto-cancel after `DEVFLOW_APPROVAL_TIMEOUT_SECONDS` (default: 300 s) with no response.
- Stale approvals (after timeout) are discarded.

### 3.6 Test Runner

- Launches `pytest` as a **subprocess** with a hard timeout.
- Working directory confined to `sample_app/`.
- Arguments passed as a **list**, never a shell string — no injection risk.
- stdout/stderr captured and posted to chat.

```python
result = subprocess.run(
    ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
    capture_output=True,
    text=True,
    timeout=60,
    cwd="C:/Users/santh/DevFlow/sample_app"
)
```

---

## 4. Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Agent runtime | **Python 3.14** | Already installed; same as sample app |
| HTTP client / SSE | **httpx + sseclient-py** | Async-compatible; supports SSE streams |
| HTTP server (optional) | **FastAPI + Uvicorn** | Consistent with sample app stack |
| LLM provider | **Google Gemini 2.5 Flash** | Free API key; highest quota tier |
| Gemini SDK | `google-generativeai` | Official Python SDK |
| Git operations | **Git CLI subprocess** | No extra library; already installed |
| Test execution | **pytest subprocess** | Standard tool already in stack |
| State management | **In-memory dict keyed by `room_id`** | Sufficient for single-node hackathon demo |
| Credential storage | **`.env` file + `python-dotenv`** | Standard; never committed |
| Team chat | **Bundled Mattermost** via Switch Console | No external platform account needed |

---

## 5. Message Flow Sequence

```
User (Mattermost) → Switch → DevFlow SSE Listener
  DevFlow: "Acknowledged. Investigating..."
  DevFlow reads: git log, git show auth_service.py  [READ ONLY]
  DevFlow calls: Gemini API → root cause + fix draft
  DevFlow: "Root cause: inverted equality check on line 24.
            Proposed fix: [code diff]
            Reply 'yes' to approve or 'no' to cancel."

User: "yes"
  Switch → DevFlow SSE Listener
  DevFlow: checkout new branch devflow/fix-20261105
  DevFlow: applies fix
  DevFlow: runs pytest (subprocess, 60s timeout)
  DevFlow: "Tests passed: 7/7. Fix committed to devflow/fix-20261105."
```

---

## 6. File Structure (DevFlow Agent)

```
C:\Users\santh\DevFlow\
├── devflow/
│   ├── __init__.py
│   ├── agent.py           # Main entry point; starts SSE listener loop
│   ├── workflow.py        # 10-state machine
│   ├── git_reader.py      # Read-only git subprocess wrappers
│   ├── llm_client.py      # Gemini API calls
│   ├── approval_gate.py   # Per-room approval tracking + timeout
│   ├── test_runner.py     # pytest subprocess with timeout
│   ├── switch_client.py   # HTTP POST to Switch (post messages to rooms)
│   └── config.py          # Settings from .env
├── sample_app/            # The buggy FastAPI app DevFlow investigates
├── docs/                  # This documentation
├── .env.example           # Template — copy to .env, never commit .env
├── .gitignore             # Must include .env, .venv
├── requirements.txt
└── README.md
```

---

## 7. Environment Variables

```bash
# .env.example — copy to .env; never commit .env
GEMINI_API_KEY=your_google_ai_studio_key_here
SWITCH_AGENT_TOKEN=your_switch_bearer_token_here
SWITCH_SERVER_URL=http://localhost:3000
DEVFLOW_AGENT_NAME=devflow
DEVFLOW_APPROVED_USERS=your_mattermost_username
DEVFLOW_APPROVAL_TIMEOUT_SECONDS=300
DEVFLOW_REPO_PATH=C:/Users/santh/DevFlow
DEVFLOW_TEST_TIMEOUT_SECONDS=60
DEVFLOW_FIX_BRANCH_PREFIX=devflow/fix
```

---

## 8. Recommended Coding Agent

**→ DevFlow itself — a custom Python agent.**

Do **not** use OpenCode, Claude Code, or Aider as the primary agent. Build DevFlow as a first-class Switch agent using Python. Reasons:

| Factor | Custom Python | OpenCode | Claude Code |
|--------|---------------|----------|-------------|
| Approval gate control | ✅ Full | ❌ Not built-in | ❌ Not built-in |
| State machine | ✅ Full | ❌ Not built-in | ❌ Not built-in |
| Gemini support | ✅ Direct SDK | ✅ Via config | ❌ Anthropic only |
| Auth required | Google API key only | Google API key | Anthropic subscription |
| Switch protocol | Implement once | Wrapper needed | Wrapper needed |
| Hackathon setup time | Low | Medium | High |

**OpenCode** is a good fallback if Gemini LLM calls are needed inside a richer coding TUI, but for DevFlow's structured workflow, a custom agent is simpler and faster to build in four days.

