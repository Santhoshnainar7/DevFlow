"""
Git workflow and repository boundary management for DevFlow.

Enforces workspace restrictions, isolates fixes to dedicated branches,
guards against overwriting developer changes, and computes code diffs.
"""

import difflib
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger("git_workflow")

AUTHORIZED_EXTENSIONS = {".py", ".json", ".toml", ".yaml", ".yml", ".md", ".txt"}


class GitWorkflow:
    """Manages safe, branch-isolated code modifications within a repository."""

    def __init__(self, repo_path: Path, branch_prefix: str = "devflow/fix"):
        self.repo_path = Path(repo_path).resolve()
        self.branch_prefix = branch_prefix
        self.current_branch: str = "main"
        self._initial_branch: Optional[str] = None
        self._file_backups: Dict[str, Optional[str]] = {}  # rel_path -> original_content

    def is_git_repo(self) -> bool:
        """Returns True if the target repository contains a .git directory."""
        return (self.repo_path / ".git").is_dir()

    def check_uncommitted_changes(self) -> Tuple[bool, str]:
        """
        Verifies repository state before starting.
        Returns (True, message) if unrelated uncommitted developer changes exist.
        """
        if not self.is_git_repo():
            # If not a git repo, check is skipped
            return False, ""

        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            stdout = res.stdout.strip()
            if stdout:
                changed_items = [line.strip() for line in stdout.splitlines()]
                msg = f"Repository has uncommitted developer changes: {'; '.join(changed_items[:3])}"
                logger.warning(msg)
                return True, msg
            return False, ""
        except Exception as e:
            logger.error(f"Error checking git status: {e}")
            return False, ""

    def create_isolated_branch(self, issue_id: str) -> str:
        """
        Creates and checks out an isolated working branch.
        Never works directly on main/master.
        """
        clean_issue = issue_id.lower().replace("-", "")
        timestamp = int(time.time())
        branch_name = f"{self.branch_prefix}-{clean_issue}-{timestamp}"

        if self.is_git_repo():
            try:
                # Capture current branch
                curr = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(self.repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=False,
                )
                self._initial_branch = curr.stdout.strip() or "main"

                # Create and checkout branch
                checkout_res = subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    cwd=str(self.repo_path),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=False,
                )
                if checkout_res.returncode == 0:
                    logger.info(f"Checked out isolated branch '{branch_name}' (from '{self._initial_branch}')")
                else:
                    logger.warning(f"Could not checkout git branch: {checkout_res.stderr.strip()}")
            except Exception as e:
                logger.error(f"Failed to create git branch {branch_name}: {e}")

        self.current_branch = branch_name
        return branch_name

    def validate_target_path(self, relative_path: str) -> Tuple[bool, Optional[Path], str]:
        """
        Validates that target file is within authorized workspace boundaries.
        Rejects directory traversal, absolute paths, and unauthorized file extensions.
        """
        try:
            # Check for absolute paths
            path_obj = Path(relative_path)
            if path_obj.is_absolute() or relative_path.startswith("/") or relative_path.startswith("\\"):
                return False, None, f"Unauthorized file: Absolute paths are not permitted: '{relative_path}'"

            target = (self.repo_path / relative_path).resolve()

            # Prevent path traversal outside repository
            if not target.is_relative_to(self.repo_path):
                return False, None, f"Unauthorized file: Path '{relative_path}' traverses outside workspace."

            # Extension check
            if target.suffix.lower() not in AUTHORIZED_EXTENSIONS:
                return False, None, f"Unauthorized file extension '{target.suffix}'. Allowed: {AUTHORIZED_EXTENSIONS}"

            return True, target, ""
        except Exception as e:
            return False, None, f"Path validation error: {str(e)}"

    def apply_patch(self, relative_path: str, new_content: str) -> Tuple[bool, str]:
        """
        Applies code modifications to authorized file after taking an in-memory backup.
        """
        is_valid, target_path, err = self.validate_target_path(relative_path)
        if not is_valid or target_path is None:
            return False, err

        try:
            # Backup original content
            if relative_path not in self._file_backups:
                if target_path.exists():
                    self._file_backups[relative_path] = target_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                else:
                    self._file_backups[relative_path] = None  # New file

            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(new_content, encoding="utf-8")
            logger.info(f"Applied patch to {relative_path} ({len(new_content)} bytes)")
            return True, relative_path
        except Exception as e:
            logger.error(f"Failed to apply patch to {relative_path}: {e}")
            return False, f"Write error: {str(e)}"

    def compute_diff(self) -> str:
        """
        Generates unified diff of all modifications made by this workflow.
        Works consistently via difflib or git diff.
        """
        diff_chunks: List[str] = []

        # 1. Use git diff if available
        if self.is_git_repo():
            try:
                res = subprocess.run(
                    ["git", "diff"],
                    cwd=str(self.repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=False,
                )
                if res.stdout.strip():
                    return res.stdout.strip()
            except Exception:
                pass

        # 2. Fallback to difflib across backed-up files
        for rel_path, old_content in self._file_backups.items():
            target = (self.repo_path / rel_path).resolve()
            new_content = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
            old_lines = old_content.splitlines(keepends=True) if old_content else []
            new_lines = new_content.splitlines(keepends=True)

            diff = difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
            )
            diff_text = "".join(diff)
            if diff_text:
                diff_chunks.append(diff_text)

        return "\n".join(diff_chunks)

    def revert_workflow_changes(self):
        """
        Safely reverts only the files modified by this workflow.
        Preserves all unrelated files.
        """
        logger.info(f"Reverting {len(self._file_backups)} workflow-modified files...")
        for rel_path, original in self._file_backups.items():
            target = (self.repo_path / rel_path).resolve()
            try:
                if original is None:
                    # File was newly created, remove it
                    if target.exists():
                        target.unlink()
                else:
                    # Restore original content
                    target.write_text(original, encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to revert {rel_path}: {e}")

        # Switch back to initial branch if git repo
        if self.is_git_repo() and self._initial_branch:
            try:
                subprocess.run(
                    ["git", "checkout", self._initial_branch],
                    cwd=str(self.repo_path),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=False,
                )
            except Exception:
                pass
