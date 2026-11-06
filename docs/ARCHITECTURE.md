# DevFlow System Architecture

## 1. Executive Architecture Overview

DevFlow is an autonomous, human-in-the-loop software engineering agent built for the SandboxAQ "Flip the Switch" Hackathon. It integrates team chat platforms (Switch Console and Discord) directly with version control systems and local repositories to autonomously investigate bug reports, synthesize targeted patches, enforce a cryptographically secure approval gate, and run automated verification suites.

```mermaid
flowchart TD
    subgraph ChatPlatforms["1. Collaboration Tier (Switch & Discord)"]
        A1["Developer in Discord / Switch"] -->|"@devflow bug report"| A2["Switch Local Server (v0.40.1)"]
        A2 -->|"REST & SSE Gateway"| A3["Switch Bot Connector"]
    end

    subgraph CoreAgent["2. DevFlow Autonomous Backend (FastAPI)"]
        B1["TriageWorkflow State Machine"]
        B2["Bug Classifier & AST Inspector"]
        B3["Read-Only Reproduction Runner"]
        B4["Approval Manager (Gatekeeper)"]
        B5["Fix Executor (Git Branch Isolation)"]
        B6["Controlled Test Runner (Pytest Subprocess)"]
        B7["Switch & Engineering Reporter"]
    end

    subgraph SecurityGate["3. Human Authorization Boundary"]
        G1{"Human Developer Decision"}
        G2["Allowlist: DEVFLOW_APPROVED_USERS"]
        G3["Single-Use Token: EXEC-<id>-<nonce>"]
    end

    subgraph VersionControl["4. Workspace & Repository Tier"]
        C1["Isolated Git Branch: devflow/fix-*"]
        C2["demo_repository/ (Target App)"]
        C3["GitHub REST API v3 (PRs & Issues)"]
    end

    A3 -->|"Dispatch Triage"| B1
    B1 -->|"1. Parse & Categorize"| B2
    B2 -->|"2. Read-only AST Scan"| C2
    B2 -->|"3. Reproduction Probe"| B3
    B3 -->|"4. 11-Field Diagnosis"| B7
    B7 -->|"Stage 3 & 4 Prompts"| A2
    
    A1 -->|"APPROVE <id>"| G1
    G1 -->|"Validate Identity"| G2
    G2 -->|"Issue Single-Use Token"| G3
    G3 -->|"Unlock Execution Gate"| B4
    
    B4 -->|"Initialize Workspace"| B5
    B5 -->|"Checkout Working Branch"| C1
    B5 -->|"Apply Patch"| C1
    B5 -->|"Execute Tests"| B6
    B6 -->|"Subprocess with Timeout"| C2
    
    B6 -->|"Verify Results"| B5
    B5 -->|"Build Summary"| B7
    B7 -->|"Stage 8 Final Report"| A2
    B7 -->|"Optional PR Opening"| C3
```

---

## 2. Core Subsystems

### 2.1 Collaboration & Messaging Layer
- **Switch Console (`v0.40.1`)**: Serves as the team collaboration hub, running on `127.0.0.1:52774`.
- **Discord Gateway Bridge**: Bridged via Switch's native Discord connector (`#bug-reports`), providing bi-directional webhook and websocket communications directly into developer chat rooms.
- **Codex Agent Worker**: Configured with autonomous reasoning instructions (`AGENTS.md`) to guide tool execution and report drafting.

### 2.2 Bug Investigation Engine (Phase 03)
The investigation engine conducts rigorous, read-only analysis without making any modifications to disk:
1. **Classifier (`BugClassifier`)**: Categorizes bugs into 8 official categories (`Authentication`, `API failures`, `Database errors`, `Frontend issues`, `Validation errors`, `Performance problems`, `Dependency issues`, `Unknown`) using heuristic pattern recognition and severity scoring.
2. **Repository Inspector (`RepositoryInspector`)**: Uses Python's native `ast` module to extract classes, functions, and imports from genuine repository files. Enforces directory traversal barriers to block unauthorized access outside the repository root.
3. **Reproduction Runner (`ReproductionRunner`)**: Probes existing test suites (`pytest`) in read-only mode to capture real stack traces and exit codes. Distinguishes confirmed facts from hypotheses.

### 2.3 Human Approval Gate (Phase 04)
A strict, server-side authorization barrier between diagnosis and code modification:
- **Zero-Write Invariant**: Not a single file can be created, modified, or deleted without a valid execution token.
- **Allowlist RBAC**: Validates sender against `DEVFLOW_APPROVED_USERS`. Chat messages from unauthorized accounts are strictly blocked.
- **Single-Use Execution Tokens**: Cryptographically random tokens (`EXEC-<issue_id>-<nonce>`) valid for 15 minutes. Automatically consumed upon branch creation to prevent replay attacks.
- **Persistent Audit Log**: All approvals, rejections, cancellations, and timestamps are persisted to `data/approvals.json`.

### 2.4 Controlled Code Fixing Engine (Phase 05)
1. **Pre-Flight Repository Verification**: Inspects `git status` to ensure working directory is clean before modifying files.
2. **Branch Isolation**: Never modifies `main` or `master` directly. Checkouts an isolated branch: `devflow/fix-<issue_id>-<timestamp>`.
3. **Workspace Boundary Enforcement**: Validates that all target paths remain strictly inside the authorized repository workspace.
4. **Controlled Subprocess Execution**: Pytest runs with explicit argument arrays, `shell=False`, and hard execution timeouts (default: 30s) to prevent hang conditions.
5. **Atomic Auto-Rollback**: If tests fail or timeout occurs, all uncommitted changes on the fix branch are automatically reverted, preserving the clean state of the target application.

### 2.5 Reporting & Version Control Integration (Phase 06)
- **8-Stage Switch Lifecycle**: Dispatches progressive updates (Bug received, Investigation started, Investigation completed, Approval requested, Approval decided, Fix started, Tests completed, Final summary).
- **GitHub Integration**: Direct REST API v3 client (`httpx`). Opens pull requests for human review and creates tracking issues with Switch backlinks. Rejects `main` as head branch and includes token masking and offline fallback.

---

## 3. End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer (Chat)
    participant Switch as Switch / Discord
    participant Engine as DevFlow Engine
    participant Gate as Approval Gate
    participant Git as Git & Pytest Runner
    participant GH as GitHub API

    Dev->>Switch: "Bug: login returns 500 on bad password"
    Switch->>Engine: Dispatch InvestigationRequest
    Note over Engine: Stage 1: Bug Received
    Note over Engine: Stage 2: Investigation Started
    Engine->>Git: Read AST & Inspect test_auth.py
    Git-->>Engine: AST Symbols & Test Results
    Note over Engine: Stage 3: Investigation Completed
    Engine->>Switch: Post 11-Field Investigation Report
    Note over Engine: Stage 4: Approval Requested
    Engine->>Switch: Post APPROVE/REJECT Prompt (APP-DF-001)

    Dev->>Switch: "APPROVE DF-001"
    Switch->>Gate: Validate user & issue ID
    Gate->>Gate: Check DEVFLOW_APPROVED_USERS & Expiration
    Gate-->>Engine: Grant EXEC-DF-001 Token
    Note over Engine: Stage 5: Approval Decided

    Engine->>Git: Consume Token & Verify git status
    Note over Engine: Stage 6: Fix Started
    Git->>Git: Checkout devflow/fix-df-001 branch
    Git->>Git: Apply patch to app/routers/auth.py
    Note over Engine: Stage 7: Tests Completed
    Git->>Git: Run pytest tests/test_auth.py
    Git-->>Engine: 7/7 Passed (Exit Code 0)

    Note over Engine: Stage 8: Final Report Published
    Engine->>GH: Create PR devflow/fix-df-001 -> main
    GH-->>Engine: PR #42 Created
    Engine->>Switch: Publish Final Engineering Report with PR Link
    Switch-->>Dev: Review completed engineering summary
```

---

## 4. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.14.3 | Core runtime for backend, parser, and agents |
| **API Framework** | FastAPI 0.115.8 / Starlette | High-performance asynchronous REST API |
| **Data Validation** | Pydantic v2.14.1 | Schema validation, typing, and serialization |
| **Web Server** | Uvicorn 0.34.0 | ASGI web server |
| **HTTP Client** | HTTPX 0.28.1 | Asynchronous HTTP client for GitHub REST API |
| **Test Runner** | Pytest 9.2.0 | Automated unit, regression, and scenario testing |
| **Messaging & Agents** | Switch Console v0.40.1 | Team chat, agent orchestration, and Discord gateway |
| **Target App** | FastAPI + SQLite (Demo Repo) | Baseline sample application for bug scenarios |
