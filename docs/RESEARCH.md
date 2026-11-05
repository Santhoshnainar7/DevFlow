# Switch Platform — Technical Research

> **Phase**: 00 — Reconnaissance only.
> **Sources**: switchagents.ai, github.com/sandbox-quantum/switch, devtoolsacademy.com, wemakedevs.org.
> **Date**: 2026-11-05

---

## 1. What Is Switch?

Switch is an **open-source, multi-agent collaboration platform** built by **SandboxAQ** (repo: `github.com/sandbox-quantum/switch`). It acts as an infrastructure bridge that connects AI coding agents into team messaging environments — Slack, Microsoft Teams, Discord, Telegram, and Mattermost — as named, collaborative participants.

Switch is the platform powering the **"Flip the Switch" Hackathon**.

---

## 2. Core Architecture

```
Team Chat (Slack / Discord / Mattermost / Teams / Telegram)
        │  messages & @mentions
        ▼
  Switch Console (desktop app)
        │  spins up and manages Docker containers
        ▼
  Switch Local Server (Docker-based coordination layer)
        │  routes room events to agents
        ▼
  Agent Bridge (SSE stream out / HTTP POST in)
        │  standardised open protocol
        ▼
  Your Coding Agent (custom Python / Claude Code / OpenCode / etc.)
        │  reads repo, executes logic, responds
        ▼
  Git Repository (local)
```

**Rooms** are the fundamental unit. Every channel maps to a Switch Room. Agents join rooms and receive/send messages as teammates.

---

## 3. Installation

### 3.1 Switch Console (Desktop GUI)

Switch provides a **Switch Console** desktop application that orchestrates Docker containers locally.

| Platform | Installer |
|----------|-----------|
| **Windows** | `switch-console-x64.exe` or `switch-console-x64.msi` |
| macOS Apple Silicon | `switch-console-arm64.dmg` |
| macOS Intel | `switch-console-x64.dmg` |
| Linux | `.AppImage`, `.deb`, or `.rpm` |

**Windows Setup Steps:**
1. Download the Windows installer from the [official Switch releases page](https://github.com/sandbox-quantum/switch/releases) or from `switchagents.ai`.
2. Run the installer.
3. Launch **Switch Console**.
4. The Console auto-provisions the required Docker containers (local server + bundled Mattermost).
5. Interact with **switch-buddy** (the built-in onboarding assistant) to configure your first agent.

> [!IMPORTANT]
> Docker Desktop must be **running** before launching Switch Console. See `ENVIRONMENT_SETUP.md` for the Docker fix.

### 3.2 Self-Hosted via Docker Compose (Alternative)

For headless or CI setups, Switch can be self-hosted directly:

```bash
git clone https://github.com/sandbox-quantum/switch.git
cd switch
docker compose up -d
```

The local Switch server becomes available at `http://localhost:3000`.

### 3.3 Documentation MCP Server

Switch exposes its docs as an MCP server for agents to read:

```bash
# Claude Code:
claude mcp add switch-docs --transport http https://docs.switchagents.ai/mcp

# OpenAI Codex:
codex mcp add switch-docs --url https://docs.switchagents.ai/mcp
```

---

## 4. Windows Support

✅ **Windows is officially supported** via:
- Native Windows installer (`.exe` / `.msi`)
- Docker Desktop for Windows (Hyper-V or WSL2 backend handles Linux containers)
- No manual WSL configuration required for typical Switch usage

---

## 5. Local Deployment

Switch runs **entirely locally**. No cloud server or external hosting is required for the hackathon.

| Container | Purpose |
|-----------|---------|
| Switch coordination server | Routes room events between chat and agents |
| Mattermost (bundled) | Built-in team chat — no external Slack/Discord needed |

---

## 6. Agent Connection Protocol

Switch uses a clean, platform-agnostic, two-direction protocol:

| Direction | Transport | Description |
|-----------|-----------|-------------|
| Switch → Agent | **Server-Sent Events (SSE)** | Streams room messages and events to your agent |
| Agent → Switch | **HTTP POST** | Agent sends replies, status updates, and messages |

Any agent that speaks this protocol can join a Switch room.

### 6.1 Incoming SSE Event Format (Switch → Agent)

Your agent opens an SSE connection to: `GET /v1/agent/events`

Each event looks like:
```json
{
  "event": "message.posted",
  "data": {
    "room_id": "room_abc123",
    "author_id": "user_xyz789",
    "author_type": "human",
    "body": "@devflow login endpoint returns 200 for wrong password",
    "posted_at": "2026-11-05T16:00:00Z"
  }
}
```

Key fields:
- `room_id` — identifies the room; used for all state keying and reply routing.
- `author_type` — `"human"` or `"agent"` (filter out your own messages to avoid loops).
- `body` — the raw message text, including `@agent-name` mentions.

### 6.2 Outgoing HTTP POST Format (Agent → Switch)

To post a reply to a room:

```
POST /v1/rooms/{room_id}/messages
Authorization: Bearer <SWITCH_AGENT_TOKEN>
Content-Type: application/json

{
  "room_id": "room_abc123",
  "body": "Acknowledged. Investigating the login endpoint...",
  "format": "markdown"
}
```

### 6.3 Agent Token

The Switch Console generates a **Bearer token** per registered agent. This token is passed in the `Authorization` header on both the SSE connection and the HTTP POST calls. Store it in an environment variable — never hard-code it.

---

## 7. Switch Console Features

| Feature | Description |
|---------|-------------|
| Local server management | Start/stop Switch containers from the UI |
| Agent registration | Register agents by name + endpoint URL + room assignments |
| switch-buddy | Built-in AI onboarding assistant |
| Room management | Create and assign rooms |
| Bundled Mattermost | Built-in chat platform (no external account required) |
| External chat platforms | Optional: Slack, Teams, Discord, Telegram, Mattermost |

---

## 8. Session Management

- State is room-scoped — all history and context keyed by `room_id`.
- Agents receive the full message history per room through the SSE stream.
- Multiple agents can share a room simultaneously.
- Your agent maintains its own in-memory or persistent session state per `room_id`.
- Kill switches can terminate compromised sessions.

---

## 9. Permissions and Security

> [!NOTE]
> Switch is a routing layer. Security enforcement at the **agent level** is the developer's responsibility.

| Concern | Switch Mechanism | Agent-Level Mechanism |
|---------|-----------------|----------------------|
| Agent identity | Named registration + Bearer token in Console | Verify token on every request |
| Authorized approvers | Room-level agent-addressing | Allowlist of approved `author_id` values in agent code |
| Credential protection | Switch does not store agent credentials | Use `.env` environment variables; never commit |
| Message authenticity | HMAC-signed payloads where applicable | Verify signatures before processing |
| Network isolation | Local deployment only by default | Docker network isolation for containers |

---

## 10. Supported Coding Agents

Switch is **agent-agnostic** — any service implementing the SSE/HTTP protocol can join a room.

| Agent | Publisher | Notes |
|-------|-----------|-------|
| **Claude Code** | Anthropic | Mentioned in official Switch docs as primary example |
| **OpenAI Codex** | OpenAI | Supported via MCP |
| **OpenCode** | opencode.ai | Open-source; supports Gemini via Google AI Studio API key |
| **Aider** | — | Terminal/CLI-driven agent loops |
| **Cursor** | Anysphere | Via Switch protocol |
| **Google ADK agents** | Google | Via MCP + custom HTTP |
| **Custom Python agents** | Your code | Full SSE/HTTP implementation — DevFlow's approach |

---

## 11. Known Limitations and Unknowns

| Item | Status |
|------|--------|
| Official Python SDK for Switch agents | ❓ Not found — protocol is DIY |
| Exact Switch Console download URL path | ⚠️ Check `switchagents.ai` directly — may require sign-in |
| Precise authentication token format | ⚠️ Verify after Switch Console installation |
| Rate limits on local Switch server | ❓ Assumed none for local deployment |
| Windows Defender / antivirus blocking Docker | ⚠️ Potential issue — test after Docker fix |
| Mattermost-specific message field names | ⚠️ May differ from generic Switch protocol — verify in docs MCP |

