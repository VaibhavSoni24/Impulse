"""Data models and enums for failure classification (Stage 18 / Candidate E9).

Defines the eight canonical failure classes, evidence strength levels,
typed classification context, and structured classification results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from local.task_state.models import TaskState


class FailureClass(str, Enum):
    """Canonical eight failure categories (PLAN.md Stage 18).

    Stable machine-readable string identifiers.
    """

    ENVIRONMENT = "ENVIRONMENT"
    COMMAND = "COMMAND"
    PRE_EXISTING_FAILURE = "PRE_EXISTING_FAILURE"
    REGRESSION = "REGRESSION"
    INCOMPLETE_FIX = "INCOMPLETE_FIX"
    WRONG_HYPOTHESIS = "WRONG_HYPOTHESIS"
    NEW_EDGE_CASE = "NEW_EDGE_CASE"
    UNKNOWN = "UNKNOWN"


class EvidenceStrength(str, Enum):
    """Confidence / certainty level based on observable evidence."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    UNKNOWN = "unknown"


# Maximum allowed length for snippet fields to prevent TaskState bloat
MAX_SNIPPET_LENGTH = 1000
MAX_OUTPUT_SUMMARY_LENGTH = 1500


@dataclass
class FailureClassificationContext:
    """Bounded, typed context provided to the failure classifier.

    Contains verifiable signals from test execution, commands, and diffs.
    Secrets and excessive logs must be sanitized before creating this context.
    """

    command: str = ""
    exit_code: int = 1
    stdout: str = ""
    stderr: str = ""
    test_output: str = ""
    modified_files: list[str] = field(default_factory=list)
    baseline_result: str | None = None  # e.g., "PASSED", "FAILED", "UNEXECUTED", or None
    current_hypothesis: str | None = None
    is_related_to_changes: bool | None = None
    environment_details: str | None = None
    previous_test_result: str | None = None
    is_edge_case: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Sanitizes snippet lengths to prevent memory bloat."""
        if len(self.stdout) > MAX_OUTPUT_SUMMARY_LENGTH:
            self.stdout = self.stdout[:MAX_OUTPUT_SUMMARY_LENGTH] + "... [truncated]"
        if len(self.stderr) > MAX_OUTPUT_SUMMARY_LENGTH:
            self.stderr = self.stderr[:MAX_OUTPUT_SUMMARY_LENGTH] + "... [truncated]"
        if len(self.test_output) > MAX_OUTPUT_SUMMARY_LENGTH:
            self.test_output = self.test_output[:MAX_OUTPUT_SUMMARY_LENGTH] + "... [truncated]"


@dataclass
class FailureClassification:
    """Structured result of failure classification."""

    failure_class: FailureClass
    evidence_strength: EvidenceStrength
    rationale: str
    relevant_command: str = ""
    evidence: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Converts classification record to dictionary."""
        return {
            "failure_class": self.failure_class.value,
            "evidence_strength": self.evidence_strength.value,
            "rationale": self.rationale,
            "relevant_command": self.relevant_command,
            "evidence": list(self.evidence),
            "timestamp": self.timestamp,
        }

    def format_summary(self) -> str:
        """Produces a compact, human-readable triage summary."""
        evidence_str = "; ".join(self.evidence) if self.evidence else "None"
        return (
            f"=== Failure Classification ===\n"
            f"Class:    {self.failure_class.value}\n"
            f"Strength: {self.evidence_strength.value}\n"
            f"Command:  {self.relevant_command or 'N/A'}\n"
            f"Rationale: {self.rationale}\n"
            f"Evidence: {evidence_str}\n"
            f"=============================="
        )

    def integrate_into_task_state(self, state: TaskState, traceback_snippet: str = "") -> None:
        """Records the classification into TaskState.failures without raw log bloat."""
        clean_tb = traceback_snippet[:MAX_SNIPPET_LENGTH] if traceback_snippet else ""
        description = f"[{self.evidence_strength.value}] {self.rationale}"
        if self.evidence:
            description += f" (Evidence: {'; '.join(self.evidence[:3])})"
        state.add_failure(
            failure_type=self.failure_class.value,
            description=description,
            traceback_snippet=clean_tb,
            resolved=False,
        )
