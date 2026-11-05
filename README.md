# DevFlow

> **Autonomous, Switch-Connected AI Teammate for Bug Investigation & Fix Workflows**  
> Developed for the *Flip the Switch Hackathon*.

---

## 1. Overview

DevFlow connects to team collaboration platforms (via the **Switch Agent Platform**) to act as an automated developer teammate. When a bug report or test regression is posted to a room, DevFlow:

1. **Acknowledges** the report immediately in chat.
2. **Inspects** the connected repository using read-only Git operations.
3. **Investigates** the root cause using Google Gemini.
4. **Drafts** a clean, targeted fix proposal.
5. **Requests explicit human approval** before modifying any code.
6. **Applies** only approved fixes on an isolated fix branch (`devflow/fix-*`).
7. **Executes** automated tests (`pytest`) within a strictly timed subprocess.
8. **Reports** test results and commit diffs back to the team room.

---

## 2. Project Structure

```
DevFlow/
├── backend/                  # DevFlow Agent backend service
│   └── app/
│       ├── core/             # Configuration, structured logging, centralized exceptions
│       │   ├── config.py
│       │   ├── exceptions.py
│       │   └── logging.py
│       ├── integrations/     # External platform adapters (Switch SSE, Git, LLM)
│       ├── models/           # Domain schemas and health models
│       │   └── health.py
│       ├── services/         # Business logic services
│       ├── workflows/        # Orchestration state machine
│       ├── __init__.py
│       └── main.py           # FastAPI ASGI entrypoint & health checks
├── demo_repository/          # Target repository for bug investigation demonstrations
│   ├── app/                  # Sample FastAPI login app with intentional injection points
│   └── tests/                # Automated baseline test suite (7/7 passing)
├── docs/                     # Reconnaissance, architecture & risk documentation
│   ├── ARCHITECTURE.md
│   ├── ENVIRONMENT_SETUP.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── RESEARCH.md
│   └── TECHNICAL_RISKS.md
├── scripts/                  # Development scripts
│   └── run_dev.py            # Local development server runner
├── tests/                    # Automated tests for the DevFlow backend foundation
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_exceptions.py
│   ├── test_health.py
│   └── test_logging.py
├── .env.example              # Environment variable template
├── .gitignore
├── pyproject.toml            # Pytest configuration
├── requirements.txt          # Production dependencies
└── requirements-dev.txt      # Test and development dependencies
```

---

## 3. Getting Started

### Prerequisites

- **Python 3.12+** (tested with Python 3.14.3)
- **Git**
- Optional: **Docker Desktop** (required for Phase 03 Switch local containers)

### Setup Virtual Environment

```powershell
# From C:\Users\santh\DevFlow
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install Dependencies

```powershell
pip install -r requirements.txt -r requirements-dev.txt
```

### Configuration

Copy `.env.example` to `.env` and configure your keys:

```powershell
copy .env.example .env
```

Key environment variables:
- `GEMINI_API_KEY`: Google AI Studio API key.
- `DEVFLOW_APPROVED_USERS`: Comma-separated list of chat usernames allowed to approve fixes.
- `DEVFLOW_REPO_PATH`: Path to the monitored target repository (defaults to `./demo_repository`).
- `DEVFLOW_TEST_TIMEOUT_SECONDS`: Hard timeout for test subprocess execution (default: `60`).

---

## 4. Running the Backend Service

To start the DevFlow backend in development mode:

```powershell
python scripts/run_dev.py
```

The service will be available at:
- **API Root**: `http://localhost:8000/`
- **Health Check**: `http://localhost:8000/health`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

---

## 5. Running Automated Tests

Run the backend foundation test suite:

```powershell
pytest -v
```

Run the demo repository test suite:

```powershell
cd demo_repository
pytest tests/ -v
```

---

## 6. Security Principles

1. **Read-Only Inspection**: During investigation, DevFlow is strictly restricted to read-only Git commands.
2. **Human-in-the-Loop Gate**: Fixes are never committed or applied without explicit confirmation from an allowlisted human approver.
3. **Execution Guardrails**: Tests are run as separate subprocesses with strict timeouts to prevent loops or hangs.
4. **Credential Isolation**: All keys reside exclusively in `.env` and are never committed to version control.

