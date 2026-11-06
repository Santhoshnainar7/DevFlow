# DevFlow Setup & Installation Guide

This guide walks through configuring DevFlow, connecting it to Switch Console and Discord, and running the autonomous bug fixing engine.

---

## 1. Prerequisites

- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python**: Version 3.11 or higher (Python 3.14+ supported).
- **Git**: Installed and available on your system `PATH`.
- **Switch Console**: Installed (Desktop app v0.40+ or CLI).
- **Discord** *(Optional but recommended)*: A Discord account with administrative permissions in a server.

---

## 2. Local Installation

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-username/DevFlow.git
cd DevFlow
```

### Step 2: Create and Activate Virtual Environment
```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 3. Environment Configuration

Create a `.env` file in the root directory (copy from `.env.example` if available):

```env
# Project Core
PROJECT_NAME="DevFlow"
VERSION="0.1.0"
ENVIRONMENT="development"
PORT=8000
LOG_LEVEL="INFO"
LOG_JSON=false

# Connected Repository Target
DEVFLOW_REPO_PATH="./demo_repository"

# Human Approval Gate & Security
# Comma-separated list of authorized chat handles (case-insensitive)
DEVFLOW_APPROVED_USERS="santhosh2302,lead_dev,alice_admin,admin"
DEVFLOW_APPROVAL_TIMEOUT_SECONDS=900  # 15 minutes
DEVFLOW_TEST_TIMEOUT_SECONDS=60      # 60s per pytest run

# GitHub Integration (Optional)
# If left empty, DevFlow functions 100% locally with Switch/Discord reporting
GITHUB_TOKEN=""
GITHUB_REPO="your-org/your-repo"
GITHUB_API_URL="https://api.github.com"
ENABLE_GITHUB_INTEGRATION=false
```

---

## 4. Connecting Switch Console & Discord

### Step 1: Launch Switch Console
Open Switch Console on your workstation (default port: `52774`).

### Step 2: Configure the `devflow` Agent
1. In Switch Console, go to **Your Agents** &rarr; **+ Add Agent**.
2. Set Name to `devflow`.
3. Choose provider (e.g. **Codex** or local model).
4. Set the Agent Instructions pointing to or containing the contents of `AGENTS.md`.

### Step 3: Connect Discord Messaging App
1. Go to **Admin** &rarr; **Connectors** (or Home &rarr; **Messaging apps**).
2. Click **+ Connect** &rarr; select **Discord**.
3. In [Discord Developer Portal](https://discord.com/developers/applications):
   - Create an application named `DevFlow`.
   - In **Bot** tab: Reset & copy the **Bot Token**. Enable **Server Members Intent** and **Message Content Intent**.
   - In **OAuth2** &rarr; **URL Generator**: Check `bot` scope and `Administrator` permission. Authorize the bot into your server.
4. In Switch Console: Paste the Bot Token and your Discord **Guild ID** (Server ID).
5. Complete account linking or click *Skip for now*.

### Step 4: Create the `#bug-reports` Room
1. In Switch Console, go to **Your Rooms** &rarr; **+ Create room**.
2. Select **Discord** as the messaging platform.
3. Set room name to `bug-reports`.
4. Add `devflow` as a participant.
5. Click **Create room**.

DevFlow will post an introductory greeting in your Discord `#bug-reports` channel:
> *"Hey there! Tag @devflow if you need me."*

---

## 5. Running DevFlow

### Start the Backend Server
```bash
# With virtual environment activated:
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

---

## 6. Verifying the Installation

Run the complete 62-test automated test suite:
```bash
pytest -v
```

All 62 tests across configuration, logging, investigation, human approval, code execution, reporting, and end-to-end failure scenarios should pass.

