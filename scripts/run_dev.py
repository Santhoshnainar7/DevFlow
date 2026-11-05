"""
Development runner for the DevFlow backend service.

Usage:
    python scripts/run_dev.py
"""

import sys
from pathlib import Path

# Add backend directory to sys.path so 'app' can be imported cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import uvicorn
from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"Starting {settings.PROJECT_NAME} on {settings.HOST}:{settings.PORT} (reload={settings.DEBUG or True})")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        app_dir=str(BACKEND_DIR),
    )


if __name__ == "__main__":
    main()

