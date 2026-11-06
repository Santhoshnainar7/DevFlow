"""
Triage and Investigation Workflow State Machine for DevFlow.

Manages the progression from message receipt through classification,
read-only code inspection, reproduction probe, and report generation.
"""

from enum import Enum
from typing import Dict, Optional

from app.core.exceptions import WorkflowStateError
from app.core.logging import get_logger
from app.models.investigation import InvestigationReport, InvestigationRequest
from app.services.investigation_engine import BugInvestigationEngine

logger = get_logger("workflow.triage")


class TriageState(str, Enum):
    """Linear progression states for bug triage and investigation."""

    IDLE = "IDLE"
    RECEIVED = "RECEIVED"
    CLASSIFYING = "CLASSIFYING"
    INSPECTING_REPO = "INSPECTING_REPO"
    REPRODUCING = "REPRODUCING"
    ANALYZING = "ANALYZING"
    REPORT_GENERATED = "REPORT_GENERATED"
    FAILED = "FAILED"


class TriageWorkflow:
    """Manages stateful triage and investigation workflows keyed by session/room."""

    def __init__(self, engine: Optional[BugInvestigationEngine] = None):
        self.engine = engine or BugInvestigationEngine()
        self._states: Dict[str, TriageState] = {}
        self._reports: Dict[str, InvestigationReport] = {}

    def get_state(self, session_id: str) -> TriageState:
        """Returns the current state for a given session."""
        return self._states.get(session_id, TriageState.IDLE)

    def run_investigation(
        self, session_id: str, request: InvestigationRequest
    ) -> InvestigationReport:
        """Executes the investigation workflow while updating state transitions."""
        current = self.get_state(session_id)
        if current not in (TriageState.IDLE, TriageState.REPORT_GENERATED, TriageState.FAILED):
            raise WorkflowStateError(
                message=f"Cannot initiate investigation from active state '{current.value}'.",
                current_state=current.value,
            )

        try:
            self._states[session_id] = TriageState.RECEIVED
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.RECEIVED.value}")

            self._states[session_id] = TriageState.CLASSIFYING
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.CLASSIFYING.value}")

            self._states[session_id] = TriageState.INSPECTING_REPO
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.INSPECTING_REPO.value}")

            report = self.engine.investigate(request)

            self._states[session_id] = TriageState.REPORT_GENERATED
            self._reports[session_id] = report
            logger.info(f"[{session_id}] Workflow transitioned to {TriageState.REPORT_GENERATED.value}")
            return report

        except Exception as e:
            self._states[session_id] = TriageState.FAILED
            logger.error(f"[{session_id}] Investigation workflow failed: {e}")
            raise

    def get_latest_report(self, session_id: str) -> Optional[InvestigationReport]:
        """Retrieves the latest generated report for a session."""
        return self._reports.get(session_id)

