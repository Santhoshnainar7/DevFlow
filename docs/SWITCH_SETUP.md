# Switch Environment & Coding Agent Setup Guide

> **Phase**: 02 — Switch and Coding Agent Integration  
> **Environment**: Windows 11, Switch Console v0.31.0, Local Switch Server + Bundled Mattermost  
> **Agent Name**: `devflow`  
> **Working Directory**: `C:\Users\santh\DevFlow`  

---

## 1. Overview

DevFlow connects to the team chat via **Switch Platform**. The local Switch coordination layer runs on the machine, bridging team communication (Mattermost) with coding agents.

- **Switch API Endpoint**: `http://127.0.0.1:52774`
- **Switch Agent ID**: `e496bfd5-f2bd-40f9-8bad-fd422a31328e`
- **Team Room**: `bug-reports`
- **Supported Coding Agent**: Codex / Custom agent runtime in `C:\Users\santh\DevFlow`
- **Execution Mode**: Auto mode enabled, Bypass disabled (prompts before risky operations)

---

## 2. Architecture & Components

```
┌──────────────────────────────────────────────┐
│       TEAM CHAT (Mattermost Channel)         │
│               #bug-reports                   │
│   Developer reports bugs & interacts         │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│           SWITCH CONSOLE & SERVER            │
│       Coordination Layer (Port 52774)        │
│       Routes room messages & events          │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│                DEVFLOW AGENT                 │
│       Working Directory: DevFlow/            │
│  - Issue ID tracking (DF-001, DF-002)        │
│  - Read-only code inspection                 │
│  - Bug triage & structured acknowledgement   │
└──────────────────────┬───────────────────────┘
                       │ Read-only
                       ▼
┌──────────────────────────────────────────────┐
│               DEMO REPOSITORY                │
│       C:\Users\santh\DevFlow\demo_repository │
└──────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Configuration Performed

### Step 3.1: Switch Local Environment Setup
1. Docker Desktop verified and running.
2. Switch Console application launched at:
   `C:\Users\santh\AppData\Local\Programs\Switch Console\Switch Console.exe`
3. Switch local server auto-provisioned PostgreSQL, coordination relay (`127.0.0.1:52774`), and bundled Mattermost.

### Step 3.2: Room Creation
1. Created public engineering room: `#bug-reports`.
2. Added participants:
   - Developer (Admin)
   - `switch-buddy` (Platform assistant)
   - `devflow` (Autonomous coding agent)

### Step 3.3: Agent Identity & System Instructions
Configured agent identity as **`devflow`** with the following triage instructions:

```text
When a developer reports a bug:
- Acknowledge the report immediately.
- Generate a unique issue identifier (e.g., DF-001, DF-002).
- Summarize the reported problem.
- Ask for missing information when necessary (reproduction steps, expected vs actual behavior).
- Explain what investigation you intend to perform in demo_repository (inspecting code, test cases).
- DO NOT modify any repository files — perform read-only investigation only.
```

### Step 3.4: Security Policy
- **Sandbox Mode**: `workspace-write` with bypass turned **OFF**.
- **Investigation Scope**: Read-only repository inspection within `demo_repository`.
- **File Integrity**: Zero file modification permitted during bug triage.

---

## 4. Verification & Test Plan

1. **Test Case 1 (Normal message)**: Verify greeting or non-bug message handling.
2. **Test Case 2 (Complete bug report)**: Verify issue ID generation (DF-001), summary, and planned investigation.
3. **Test Case 3 (Incomplete bug report)**: Verify missing fields are identified and prompted.
4. **Test Case 4 (Two separate reports)**: Verify distinct issue IDs and conversation tracking.
5. **Test Case 5 (Conversation isolation)**: Verify responses remain in `#bug-reports`.
6. **Test Case 6 (Zero file modifications)**: Verify `git status` remains clean across all repositories.

