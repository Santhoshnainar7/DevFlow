"""
Safe reproduction runner for the DevFlow Bug Investigation Engine.

Attempts to reproduce reported issues through read-only test execution
or targeted request probes. Never modifies repository files.
Accurately reports whether reproduction succeeded or failed.
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Optional

from app.core.logging import get_logger
from app.models.investigation import ReproductionResult

logger = get_logger("reproduction_runner")


class ReproductionRunner:
    """Safely executes read-only reproduction attempts."""

    def __init__(self, repo_path: Path, timeout_seconds: int = 20):
        self.repo_path = Path(repo_path).resolve()
        self.timeout_seconds = timeout_seconds

    def attempt_reproduction(
        self,
        target_test_files: List[str],
        keywords: List[str],
    ) -> ReproductionResult:
        """
        Executes a targeted test run against the repository to see if
        a relevant test fails (reproducing the reported failure).
        """
        if not self.repo_path.exists():
            return ReproductionResult(
                attempted=False,
                reproduced=False,
                summary="Reproduction skipped: Repository path does not exist on disk.",
            )

        # Look for existing test files to execute
        test_args: List[str] = []
        if target_test_files:
            # Pick first relevant test file
            rel_test = target_test_files[0]
            test_path = self.repo_path / rel_test
            if test_path.is_file():
                test_args = [rel_test]

        if not test_args:
            # Look for standard test directory
            tests_dir = self.repo_path / "tests"
            if tests_dir.is_dir():
                test_args = ["tests"]
            else:
                return ReproductionResult(
                    attempted=False,
                    reproduced=False,
                    summary="No automated test suite discovered for reproduction attempt.",
                )

        # Build command: python -m pytest <test_args> -v
        cmd = [sys.executable, "-m", "pytest"] + test_args + ["-v", "--tb=short"]

        # If keyword filter available, narrow down test
        keyword_filter = None
        for k in ["login", "auth", "wrong_password", "unknown_user", "empty"]:
            if k in keywords:
                keyword_filter = k
                break

        if keyword_filter:
            cmd.extend(["-k", keyword_filter])

        cmd_str = " ".join(cmd)
        logger.info(f"Executing safe reproduction probe: {cmd_str} in {self.repo_path}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )

            # Pytest returns 0 on all tests passing, 1 on test failures
            exit_code = result.returncode
            stdout_clean = result.stdout.strip() if result.stdout else ""
            stderr_clean = result.stderr.strip() if result.stderr else ""

            if exit_code == 1:
                # Test failed -> Bug reproduced!
                return ReproductionResult(
                    attempted=True,
                    reproduced=True,
                    command=cmd_str,
                    exit_code=exit_code,
                    summary=f"Bug successfully reproduced: Test execution exited with code 1 (failure observed).",
                    stdout=stdout_clean[-1500:] if len(stdout_clean) > 1500 else stdout_clean,
                    stderr=stderr_clean[-1500:] if len(stderr_clean) > 1500 else stderr_clean,
                )
            elif exit_code == 0:
                # All tests passed -> Bug not currently reproducible via existing tests
                return ReproductionResult(
                    attempted=True,
                    reproduced=False,
                    command=cmd_str,
                    exit_code=exit_code,
                    summary="Reproduction attempted: All executed tests passed cleanly. Symptom not reproduced on checked-in code.",
                    stdout=stdout_clean[-500:] if len(stdout_clean) > 500 else stdout_clean,
                )
            else:
                # Other error (e.g. pytest error code 2, 3, 4, 5)
                return ReproductionResult(
                    attempted=True,
                    reproduced=False,
                    command=cmd_str,
                    exit_code=exit_code,
                    summary=f"Reproduction attempt encountered test execution error (exit code {exit_code}).",
                    stdout=stdout_clean[-500:] if len(stdout_clean) > 500 else stdout_clean,
                    stderr=stderr_clean[-500:] if len(stderr_clean) > 500 else stderr_clean,
                )

        except subprocess.TimeoutExpired:
            return ReproductionResult(
                attempted=True,
                reproduced=False,
                command=cmd_str,
                summary=f"Reproduction attempt timed out after {self.timeout_seconds} seconds.",
            )
        except Exception as e:
            logger.error(f"Reproduction command failed: {e}")
            return ReproductionResult(
                attempted=True,
                reproduced=False,
                command=cmd_str,
                summary=f"Reproduction execution failed: {str(e)}",
            )

