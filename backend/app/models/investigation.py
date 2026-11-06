"""
Domain models and schemas for the DevFlow Bug Investigation Engine.

Defines bug categories, severity levels, file inspection findings,
reproduction attempts, and structured investigation reports.
"""

from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class BugCategory(str, Enum):
    """Standardized classification of software bugs."""

    AUTHENTICATION = "Authentication"
    API_FAILURES = "API failures"
    DATABASE_ERRORS = "Database errors"
    FRONTEND_ISSUES = "Frontend issues"
    VALIDATION_ERRORS = "Validation errors"
    PERFORMANCE_PROBLEMS = "Performance problems"
    DEPENDENCY_ISSUES = "Dependency issues"
    UNKNOWN = "Unknown"


class Severity(str, Enum):
    """Impact and urgency severity levels."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class CodeSymbol(BaseModel):
    """An identified code symbol (function or class) in an inspected source file."""

    name: str
    symbol_type: str  # 'function', 'async_function', 'class'
    line_number: int
    end_line_number: Optional[int] = None
    docstring: Optional[str] = None


class FileInspection(BaseModel):
    """Inspection metadata and extracted AST symbols from a real repository file."""

    relative_path: str
    exists: bool = True
    size_bytes: int = 0
    functions: List[str] = Field(default_factory=list)
    classes: List[str] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)
    snippet: Optional[str] = None


class ReproductionResult(BaseModel):
    """Outcome of attempting to safely reproduce a reported bug."""

    attempted: bool = False
    reproduced: bool = False
    command: Optional[str] = None
    exit_code: Optional[int] = None
    summary: str = ""
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class InvestigationRequest(BaseModel):
    """Payload requesting an automated bug investigation."""

    issue_id: Optional[str] = None
    title: Optional[str] = None
    description: str
    repository_path: Optional[str] = None
    attempt_reproduction: bool = True


class InvestigationReport(BaseModel):
    """
    Standardized, structured output of the bug investigation engine.
    Matches the required hackathon specification format.
    """

    issue_id: str
    issue_title: str
    bug_category: BugCategory
    severity: Severity
    description: str
    affected_files: List[str] = Field(default_factory=list)
    relevant_functions: List[str] = Field(default_factory=list)
    root_cause: str
    evidence: List[str] = Field(default_factory=list)
    proposed_solution: str
    testing_strategy: str
    potential_risks: str

    # Supplementary inspection metadata (optional)
    reproduction: Optional[ReproductionResult] = None
    inspections: List[FileInspection] = Field(default_factory=list)

    def to_formatted_report(self) -> str:
        """Renders the structured report string following the exact prompt specification."""
        affected = (
            ", ".join(self.affected_files)
            if self.affected_files
            else "None identified in repository"
        )
        functions = (
            ", ".join(self.relevant_functions)
            if self.relevant_functions
            else "None identified"
        )
        evidence_text = (
            "\n  - " + "\n  - ".join(self.evidence)
            if self.evidence
            else "No explicit evidence captured"
        )

        lines = [
            f"Issue ID: {self.issue_id}",
            f"Issue title: {self.issue_title}",
            f"Bug category: {self.bug_category.value}",
            f"Severity: {self.severity.value}",
            f"Description: {self.description}",
            f"Affected files: {affected}",
            f"Relevant functions: {functions}",
            f"Root cause: {self.root_cause}",
            f"Evidence: {evidence_text}",
            f"Proposed solution: {self.proposed_solution}",
            f"Testing strategy: {self.testing_strategy}",
            f"Potential risks: {self.potential_risks}",
        ]
        return "\n".join(lines)

