# Environment Setup — Verified Findings

> **Phase**: 00 — Reconnaissance only. No installations performed.
> **Date**: 2026-11-05 | **OS**: Microsoft Windows 10.0.26300 (x64)
> **Workspace**: `C:\Users\santh\DevFlow`

---

## 1. System Summary

| Property | Value |
|----------|-------|
| Operating System | Microsoft Windows NT 10.0.26300 (x64) |
| Workspace Directory | `C:\Users\santh\DevFlow` |
| Local Time Zone | IST (UTC+05:30) |
| PowerShell Version | 5.1.26100.9818 |

---

## 2. Tool Inventory

### ✅ Python

| Item | Detail |
|------|--------|
| Version | **3.14.3** |
| pip Version | **25.3** |
| pip Location | `C:\Users\santh\AppData\Local\Programs\Python\Python314\Lib\site-packages\pip` |
| `venv` module | ✅ Available |
| Status | **Fully functional** |
| Action required | None — create `.venv` at Phase 01 start |

**Commands used to verify:**
```powershell
python --version       # Python 3.14.3
pip --version          # pip 25.3
python -c "import venv; print('venv: OK')"
```

> [!NOTE]
> Python 3.14.3 is recent. FastAPI, Uvicorn, Pydantic, Pytest, and Httpx all support 3.12+. No incompatibility expected, but verify at install time.

---

### ✅ Git

| Item | Detail |
|------|--------|
| Version | **2.53.0.windows.1** |
| Repository Initialized | ✅ Yes (`C:\Users\santh\DevFlow`) |
| Current Branch | `master` |
| Commits | **None** — empty repository |
| Untracked Files | None currently (workspace reset after server restart) |
| Status | **Functional** |
| Action required | Make initial commit at start of Phase 01 |

**Commands used to verify:**
```powershell
git --version
git -C "C:\Users\santh\DevFlow" status
```

> [!IMPORTANT]
> The repository has no commits. `git log`, `git diff`, and `git show` will all fail until an initial commit is made. This is **Risk R09** — fix it first thing in Phase 01.

---

### ✅ Node.js and npm

| Item | Detail |
|------|--------|
| Node.js Version | **v22.20.0** |
| npm Version | **10.9.3** |
| Status | **Fully functional** |
| Action required | None — not required for the core Python stack |

**Commands used to verify:**
```powershell
node --version    # v22.20.0
npm --version     # 10.9.3
```

---

### ⚠️ Docker Desktop

| Item | Detail |
|------|--------|
| Docker CLI Version | **29.9.2** (build a82e528) |
| Docker Compose (standalone) | **v5.6.1** ✅ |
| Docker Engine | ❌ **Not reachable** |
| Error | `permission denied while trying to connect to the Docker daemon socket at npipe:////./pipe/docker_engine` |
| Status | **CLI installed; Engine inaccessible** |
| Action required | See fix instructions below — **this is a blocker** |

**Commands used to verify:**
```powershell
docker --version          # Docker version 29.9.2
docker-compose --version  # Docker Compose version v5.6.1
docker info               # ERROR: permission denied on npipe
```

**Root Cause:**
Either Docker Desktop is not currently running, or your Windows user account is not in the `docker-users` local security group. The Docker CLI binary is on the PATH but cannot reach the engine.

**Fix Instructions:**

**Step 1 — Start Docker Desktop** (do this first):
1. Press `Win`, search for **Docker Desktop**, and launch it.
2. Wait for the bottom-left status bar to show **"Engine running"**.
3. Rerun `docker info` in a new terminal — it should return server details.

**Step 2 — If still permission denied after Docker Desktop is running:**
Run the following in an **Administrator PowerShell** (right-click PowerShell → Run as Administrator):
```powershell
net localgroup docker-users $env:USERNAME /add
```
Then **log out and log back in** (or restart). Docker Desktop must still be launched manually.

**Step 3 — Verify fix:**
```powershell
docker info
# Should return: Server Version, OS/Arch, Containers, etc.
```

---

### ✅ PowerShell

| Item | Detail |
|------|--------|
| Version | **5.1.26100.9818** |
| Status | **Fully functional** |
| Action required | None |

> [!TIP]
> PowerShell 7+ (`pwsh`) offers better async support and error handling. Install optionally via:
> ```powershell
> winget install Microsoft.PowerShell
> ```

---

## 3. Virtual Environment — Not Yet Created

**Plan for Phase 01:**
```powershell
# From C:\Users\santh\DevFlow
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If script execution is blocked, run this once first:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

After activation, Phase 01 will install:
```powershell
pip install fastapi uvicorn pydantic
pip install pytest httpx pytest-asyncio
pip install google-generativeai python-dotenv
```

---

## 4. Disk Space

> [!WARNING]
> The sandbox environment could not read disk usage via WMI (access restricted). Run this directly in your Windows Terminal to check available space:
> ```powershell
> Get-PSDrive C | Select-Object @{N='UsedGB';E={[math]::Round($_.Used/1GB,2)}}, @{N='FreeGB';E={[math]::Round($_.Free/1GB,2)}}
> ```
> **Minimum recommended**: 10 GB free (Switch Console Docker containers use 2–4 GB).

---

## 5. Status Summary

| Tool | Version | Installed | Functional | Action |
|------|---------|-----------|------------|--------|
| Python | 3.14.3 | ✅ | ✅ | None |
| pip | 25.3 | ✅ | ✅ | None |
| venv | Built-in | ✅ | ✅ | Create `.venv` in Phase 01 |
| Git | 2.53.0.windows.1 | ✅ | ✅ | Make initial commit in Phase 01 |
| Node.js | v22.20.0 | ✅ | ✅ | None |
| npm | 10.9.3 | ✅ | ✅ | None |
| Docker CLI | 29.9.2 | ✅ | ⚠️ | Start Docker Desktop |
| Docker Compose | v5.6.1 | ✅ | ✅ (once engine runs) | None |
| Docker Engine | — | ✅ | ❌ | **Start Docker Desktop — BLOCKER** |
| PowerShell | 5.1.26100.9818 | ✅ | ✅ | None |

