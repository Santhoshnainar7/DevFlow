"""
Controlled test execution runner for DevFlow.

Enforces strictly allowlisted command execution, prevents arbitrary shell commands,
applies execution timeouts, accurately parses pytest test counts, and diagnoses failures.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("controlled_test_runner")


class TestExecutionResult(BaseModel):
    """Accurate, captured outcome of an automated test execution run."""

    __test__ = False  # Prevent pytest from treating this model as a test suite

    command: str
    exit_code: int
    tests_executed: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    is_timeout: bool = False
    is_dependency_missing: bool = False
    passed: bool = False
    failure_explanation: Optional[str] = None
    stdout: str = ""
    stderr: str = ""


class ControlledTestRunner:
    """Executes pytest suites within strict security and resource bounds."""

    def __init__(self, repo_path: Path, timeout_seconds: int = 60):
        self.repo_path = Path(repo_path).resolve()
        self.timeout_seconds = timeout_seconds

    def run_tests(
        self,
        target_tests: Optional[List[str]] = None,
        keyword_filter: Optional[str] = None,
        custom_timeout: Optional[int] = None,
    ) -> TestExecutionResult:
        """
        Executes pytest using list arguments and shell=False.
        Never executes arbitrary shell strings or external scripts.
        """
        timeout = custom_timeout if custom_timeout is not None else self.timeout_seconds

        # Construct strict command list
        cmd: List[str] = [sys.executable, "-m", "pytest"]

        if target_tests:
            # Clean and sanitize target test paths
            for t in target_tests:
                clean = t.replace("\\", "/").strip()
                if clean:
                    cmd.append(clean)
        else:
            # Default to test directory
            tests_dir = self.repo_path / "tests"
            if tests_dir.is_dir():
                cmd.append("tests")

        cmd.extend(["-v", "--tb=short"])

        if keyword_filter:
            # Sanitize keyword filter (alphanumeric and underscore only)
            sanitized_k = re.sub(r"[^a-zA-Z0-9_]", "", keyword_filter)
            if sanitized_k:
                cmd.extend(["-k", sanitized_k])

        cmd_str = " ".join(cmd)
        logger.info(f"Executing controlled test run: '{cmd_str}' in {self.repo_path} (timeout={timeout}s)")

        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )

            stdout = res.stdout or ""
            stderr = res.stderr or ""
            exit_code = res.returncode

            # Parse test counts from output
            passed_cnt, failed_cnt, total_cnt = self._parse_test_counts(stdout)

            # Check for missing dependency or import errors
            is_dep_missing = False
            failure_explanation = None

            if "ModuleNotFoundError:" in stdout or "ModuleNotFoundError:" in stderr or "ImportError:" in stdout:
                is_dep_missing = True
                match = re.search(r"(ModuleNotFoundError:.*|ImportError:.*)", stdout + "\n" + stderr)
                failure_explanation = match.group(1) if match else "Missing test dependency or import error."

            elif exit_code != 0:
                failure_explanation = self._extract_failure_reason(stdout, stderr)

            is_success = (exit_code == 0) and not is_dep_missing and (failed_cnt == 0)

            return TestExecutionResult(
                command=cmd_str,
                exit_code=exit_code,
                tests_executed=total_cnt,
                tests_passed=passed_cnt,
                tests_failed=failed_cnt,
                is_timeout=False,
                is_dependency_missing=is_dep_missing,
                passed=is_success,
                failure_explanation=failure_explanation,
                stdout=stdout[-2000:] if len(stdout) > 2000 else stdout,
                stderr=stderr[-2000:] if len(stderr) > 2000 else stderr,
            )

        except subprocess.TimeoutExpired:
            logger.warning(f"Test execution timed out after {timeout} seconds.")
            return TestExecutionResult(
                command=cmd_str,
                exit_code=-1,
                is_timeout=True,
                passed=False,
                failure_explanation=f"Execution timed out after {timeout} seconds.",
                stdout="[TIMEOUT EXPIRED]",
            )
        except Exception as e:
            logger.error(f"Test execution error: {e}")
            return TestExecutionResult(
                command=cmd_str,
                exit_code=-2,
                passed=False,
                failure_explanation=f"Execution failed to launch: {str(e)}",
                stderr=str(e),
            )

    def _parse_test_counts(self, output: str) -> tuple[int, int, int]:
        """Extracts passed, failed, and total test counts from pytest output."""
        passed = 0
        failed = 0

        # Look for summary line: e.g. "== 7 passed in 0.20s ==" or "== 1 failed, 6 passed in 0.30s =="
        passed_match = re.search(r"(\d+)\s+passed", output)
        if passed_match:
            passed = int(passed_match.group(1))

        failed_match = re.search(r"(\d+)\s+failed", output)
        if failed_match:
            failed = int(failed_match.group(1))

        total = passed + failed
        return passed, failed, total

    def _extract_failure_reason(self, stdout: str, stderr: str) -> str:
        """Extracts concise root cause of test failure from pytest traceback."""
        combined = stdout + "\n" + stderr
        # Find failure lines: e.g. "E   assert response.status_code == 401"
        error_lines = [
            line.strip()
            for line in combined.splitlines()
            if line.strip().startswith("E ") or "FAILED" in line or "AssertionError" in line
        ]
        if error_lines:
            return "; ".join(error_lines[:3])
        return "Tests exited with non-zero exit code."
