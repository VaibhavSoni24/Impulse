"""Data models and output contracts for the Scout agent (Stage 21).

Defines:
- ScoutStatus enum (LOCALIZED, PARTIALLY_LOCALIZED, AMBIGUOUS, INSUFFICIENT_EVIDENCE)
- ScoutPolicy enum (AVAILABLE, MANDATORY_UNDER_UNCERTAINTY)
- ScoutResult dataclass with structured localization findings and TaskState integration
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from local.task_state.models import TaskState

MAX_SUMMARY_LEN = 500
MAX_ITEMS_COUNT = 20


class ScoutStatus(str, Enum):
    """Categorical outcome of Scout localization investigation."""

    LOCALIZED = "LOCALIZED"
    PARTIALLY_LOCALIZED = "PARTIALLY_LOCALIZED"
    AMBIGUOUS = "AMBIGUOUS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ScoutPolicy(str, Enum):
    """Invocation policy for the Scout agent."""

    AVAILABLE = "AVAILABLE"  # E_S1: Scout available, root decides
    MANDATORY_UNDER_UNCERTAINTY = "MANDATORY_UNDER_UNCERTAINTY"  # E_S2: Scout mandatory once under uncertainty


@dataclass
class ScoutResult:
    """Structured, bounded localization evidence produced by the read-only Scout agent."""

    issue_summary: str = ""
    candidate_files: list[str] = field(default_factory=list)
    candidate_symbols: list[str] = field(default_factory=list)
    relevant_relationships: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    recommended_inspection_targets: list[str] = field(default_factory=list)
    status: ScoutStatus = ScoutStatus.AMBIGUOUS
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Converts ScoutResult to serializable dictionary representation."""
        return {
            "issue_summary": self.issue_summary[:MAX_SUMMARY_LEN],
            "candidate_files": list(self.candidate_files[:MAX_ITEMS_COUNT]),
            "candidate_symbols": list(self.candidate_symbols[:MAX_ITEMS_COUNT]),
            "relevant_relationships": list(self.relevant_relationships[:MAX_ITEMS_COUNT]),
            "evidence": list(self.evidence[:MAX_ITEMS_COUNT]),
            "unresolved_questions": list(self.unresolved_questions[:MAX_ITEMS_COUNT]),
            "recommended_inspection_targets": list(self.recommended_inspection_targets[:MAX_ITEMS_COUNT]),
            "status": self.status.value if isinstance(self.status, ScoutStatus) else str(self.status),
            "timestamp": self.timestamp,
        }

    def format_summary(self) -> str:
        """Produces a compact, human-readable summary for inspection."""
        files_str = ", ".join(self.candidate_files[:5]) if self.candidate_files else "None"
        symbols_str = ", ".join(self.candidate_symbols[:5]) if self.candidate_symbols else "None"
        evidence_str = "; ".join(self.evidence[:3]) if self.evidence else "None"
        return (
            f"=== Scout Localization Result ===\n"
            f"Status:     {self.status.value}\n"
            f"Files:      {files_str}\n"
            f"Symbols:    {symbols_str}\n"
            f"Evidence:   {evidence_str}\n"
            f"Targets:    {', '.join(self.recommended_inspection_targets[:3]) or 'None'}\n"
            f"================================="
        )

    def integrate_into_task_state(self, state: TaskState) -> None:
        """Records Scout findings into TaskState without log bloat or secret leakage."""
        clean_summary = self.issue_summary[:MAX_SUMMARY_LEN] or "Scout localization completed"
        
        # Add candidate locations discovered by Scout
        for file_path in self.candidate_files[:MAX_ITEMS_COUNT]:
            symbol = self.candidate_symbols[0] if self.candidate_symbols else ""
            state.add_candidate(
                path=file_path,
                symbol=symbol,
                rationale=f"Identified by Scout ({self.status.value})",
            )

        # Add structured observation to TaskState evidence
        status_val = self.status.value if isinstance(self.status, ScoutStatus) else str(self.status)
        observation = (
            f"Scout localization ({status_val}): {clean_summary}. "
            f"Candidates: {', '.join(self.candidate_files[:5]) or 'none'}. "
            f"Recommended: {', '.join(self.recommended_inspection_targets[:3]) or 'none'}."
        )[:MAX_SUMMARY_LEN]

        state.add_evidence(
            observation=observation,
            source="scout_agent",
            supports_hypothesis=None,
        )
