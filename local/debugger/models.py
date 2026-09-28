"""Data models and output contracts for the Debugger agent (Stage 22).

Defines:
- DebuggerStatus enum (DIAGNOSED, PARTIALLY_DIAGNOSED, AMBIGUOUS, INSUFFICIENT_EVIDENCE)
- DebuggerPolicy enum (UNAVAILABLE, AVAILABLE_ON_DIFFICULT_FAILURE)
- DebuggerResult dataclass with structured diagnostic findings and TaskState integration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

from local.failures.models import FailureClass

if TYPE_CHECKING:
    from local.task_state.models import TaskState

MAX_SUMMARY_LEN = 500
MAX_ITEMS_COUNT = 20


class DebuggerStatus(str, Enum):
    """Categorical outcome of Debugger diagnostic investigation."""

    DIAGNOSED = "DIAGNOSED"
    PARTIALLY_DIAGNOSED = "PARTIALLY_DIAGNOSED"
    AMBIGUOUS = "AMBIGUOUS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class DebuggerPolicy(str, Enum):
    """Invocation policy for the Debugger agent."""

    UNAVAILABLE = "UNAVAILABLE"  # D1: Debugger unavailable / root only
    AVAILABLE_ON_DIFFICULT_FAILURE = "AVAILABLE_ON_DIFFICULT_FAILURE"  # D2: Debugger available under DEBUGGER_TRIGGER


@dataclass
class DebuggerResult:
    """Structured, bounded diagnostic evidence produced by the read-only Debugger agent."""

    status: DebuggerStatus = DebuggerStatus.AMBIGUOUS
    failure_class: str = FailureClass.UNKNOWN.value
    failure_summary: str = ""
    likely_cause_candidates: list[str] = field(default_factory=list)
    stack_or_call_path_findings: list[str] = field(default_factory=list)
    changed_file_findings: list[str] = field(default_factory=list)
    observed_evidence: list[str] = field(default_factory=list)
    inferred_mechanisms: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    next_inspection_targets: list[str] = field(default_factory=list)
    hypothesis_update: str = ""
    unresolved_questions: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Converts DebuggerResult to a serializable dictionary representation."""
        return {
            "status": self.status.value if isinstance(self.status, DebuggerStatus) else str(self.status),
            "failure_class": self.failure_class if isinstance(self.failure_class, str) else str(self.failure_class),
            "failure_summary": self.failure_summary[:MAX_SUMMARY_LEN],
            "likely_cause_candidates": list(self.likely_cause_candidates[:MAX_ITEMS_COUNT]),
            "stack_or_call_path_findings": list(self.stack_or_call_path_findings[:MAX_ITEMS_COUNT]),
            "changed_file_findings": list(self.changed_file_findings[:MAX_ITEMS_COUNT]),
            "observed_evidence": list(self.observed_evidence[:MAX_ITEMS_COUNT]),
            "inferred_mechanisms": list(self.inferred_mechanisms[:MAX_ITEMS_COUNT]),
            "contradictions": list(self.contradictions[:MAX_ITEMS_COUNT]),
            "next_inspection_targets": list(self.next_inspection_targets[:MAX_ITEMS_COUNT]),
            "hypothesis_update": self.hypothesis_update[:MAX_SUMMARY_LEN],
            "unresolved_questions": list(self.unresolved_questions[:MAX_ITEMS_COUNT]),
            "timestamp": self.timestamp,
        }

    def format_summary(self) -> str:
        """Produces a compact, human-readable summary for inspection."""
        causes_str = ", ".join(self.likely_cause_candidates[:3]) if self.likely_cause_candidates else "None"
        obs_str = "; ".join(self.observed_evidence[:2]) if self.observed_evidence else "None"
        inf_str = "; ".join(self.inferred_mechanisms[:2]) if self.inferred_mechanisms else "None"
        contra_str = "; ".join(self.contradictions[:2]) if self.contradictions else "None"
        return (
            f"=== Debugger Diagnostic Result ===\n"
            f"Status:        {self.status.value}\n"
            f"Failure Class: {self.failure_class}\n"
            f"Likely Causes: {causes_str}\n"
            f"Observed:      {obs_str}\n"
            f"Inferred:      {inf_str}\n"
            f"Contradictions:{contra_str}\n"
            f"Update:        {self.hypothesis_update or 'None'}\n"
            f"Targets:       {', '.join(self.next_inspection_targets[:3]) or 'None'}\n"
            f"=================================="
        )

    def integrate_into_task_state(self, state: TaskState) -> None:
        """Records Debugger diagnostic findings into TaskState without log bloat or secret leakage."""
        clean_summary = self.failure_summary[:MAX_SUMMARY_LEN] or "Debugger diagnostic investigation completed"
        status_val = self.status.value if isinstance(self.status, DebuggerStatus) else str(self.status)

        # Add recommended inspection targets to candidate locations
        for target in self.next_inspection_targets[:MAX_ITEMS_COUNT]:
            if target.strip():
                state.add_candidate(
                    path=target.strip(),
                    symbol="",
                    rationale=f"Recommended for inspection by Debugger ({status_val})",
                )

        # Record structured diagnostic observation into TaskState evidence
        observation = (
            f"Debugger diagnosis ({status_val}, {self.failure_class}): {clean_summary}. "
            f"Likely cause: {', '.join(self.likely_cause_candidates[:3]) or 'none'}. "
            f"Contradictions: {', '.join(self.contradictions[:2]) or 'none'}. "
            f"Next targets: {', '.join(self.next_inspection_targets[:3]) or 'none'}."
        )[:MAX_SUMMARY_LEN]

        state.add_evidence(
            observation=observation,
            source="debugger_agent",
            supports_hypothesis=None,
        )
