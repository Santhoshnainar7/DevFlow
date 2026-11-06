"""
Safe, read-only repository inspection service for DevFlow.

Inspects source trees, parses Python ASTs to extract real functions and classes,
identifies matching test files, and searches for relevant code paths.
Never invents filenames or functions.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.core.logging import get_logger
from app.models.investigation import FileInspection

logger = get_logger("repository_inspector")

# Directories to exclude from inspection
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

# Recognized code file extensions
SOURCE_EXTENSIONS = {".py", ".toml", ".json", ".yaml", ".yml", ".md"}


class RepositoryInspector:
    """Read-only inspector for software repositories."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()

    def exists(self) -> bool:
        """Checks if the configured repository path exists on disk."""
        return self.repo_path.exists() and self.repo_path.is_dir()

    def list_source_files(self) -> List[Path]:
        """
        Recursively lists all real source files in the repository,
        skipping build, cache, and virtual environment folders.
        """
        if not self.exists():
            return []

        files: List[Path] = []
        try:
            for item in self.repo_path.rglob("*"):
                # Skip excluded directories
                if any(part in IGNORED_DIRS for part in item.parts):
                    continue
                if item.is_file() and item.suffix.lower() in SOURCE_EXTENSIONS:
                    files.append(item)
        except Exception as e:
            logger.error(f"Error enumerating files in {self.repo_path}: {e}")

        return sorted(files)

    def read_file_safe(self, relative_path: str) -> Optional[str]:
        """
        Safely reads a file within the repository boundaries.
        Guards against directory traversal attacks.
        """
        try:
            target = (self.repo_path / relative_path).resolve()
            # Ensure target is strictly inside repo_path
            if not target.is_relative_to(self.repo_path):
                logger.warning(f"Prevented path traversal attempt: {relative_path}")
                return None
            if not target.is_file():
                return None
            return target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Failed to read file {relative_path}: {e}")
            return None

    def inspect_file(self, file_path: Path) -> FileInspection:
        """
        Extracts verified AST symbols (functions, classes, imports) from a Python file.
        Never guesses or invents symbols.
        """
        try:
            rel_path = str(file_path.relative_to(self.repo_path)).replace("\\", "/")
        except ValueError:
            rel_path = file_path.name

        inspection = FileInspection(
            relative_path=rel_path,
            exists=file_path.exists(),
            size_bytes=file_path.stat().st_size if file_path.exists() else 0,
        )

        if not file_path.exists() or file_path.suffix.lower() != ".py":
            return inspection

        content = self.read_file_safe(rel_path)
        if content is None:
            return inspection

        try:
            tree = ast.parse(content, filename=str(file_path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    inspection.functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    inspection.classes.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        inspection.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        inspection.imports.append(f"{mod}.{alias.name}")

            # Deduplicate while preserving order
            inspection.functions = list(dict.fromkeys(inspection.functions))
            inspection.classes = list(dict.fromkeys(inspection.classes))
            inspection.imports = list(dict.fromkeys(inspection.imports))

            # Store brief preview snippet (first 10 lines)
            lines = content.splitlines()[:10]
            inspection.snippet = "\n".join(lines)
        except SyntaxError as e:
            logger.warning(f"Syntax error while parsing AST for {rel_path}: {e}")
        except Exception as e:
            logger.error(f"AST extraction failed for {rel_path}: {e}")

        return inspection

    def find_relevant_files(
        self, search_terms: List[str]
    ) -> List[Tuple[FileInspection, int, List[str]]]:
        """
        Scans all source files in the repository for occurrences of the search terms.
        Returns inspected files sorted by relevance score.
        """
        source_files = self.list_source_files()
        scored_results: List[Tuple[FileInspection, int, List[str]]] = []

        # Normalize search terms
        normalized_terms = [t.lower() for t in search_terms if t]

        for file_path in source_files:
            content = self.read_file_safe(
                str(file_path.relative_to(self.repo_path))
            )
            if not content:
                continue

            content_lower = content.lower()
            file_name_lower = file_path.name.lower()
            matched_terms: Set[str] = set()
            score = 0

            for term in normalized_terms:
                # Direct match in file name has highest priority
                if term in file_name_lower:
                    score += 10
                    matched_terms.add(term)

                # Count term occurrences in content
                occurrences = content_lower.count(term)
                if occurrences > 0:
                    score += min(occurrences, 5)
                    matched_terms.add(term)

            if score > 0:
                inspection = self.inspect_file(file_path)
                # Boost if term matches an exact function or class name
                for fn in inspection.functions:
                    if any(t in fn.lower() for t in normalized_terms):
                        score += 5
                for cls in inspection.classes:
                    if any(t in cls.lower() for t in normalized_terms):
                        score += 5

                scored_results.append((inspection, score, sorted(list(matched_terms))))

        # Sort descending by score
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return scored_results

    def find_test_files(self) -> List[FileInspection]:
        """Finds and inspects all test files in the repository."""
        source_files = self.list_source_files()
        test_inspections: List[FileInspection] = []

        for f in source_files:
            if "test" in f.name.lower() or "tests" in [p.lower() for p in f.parts]:
                test_inspections.append(self.inspect_file(f))

        return test_inspections

