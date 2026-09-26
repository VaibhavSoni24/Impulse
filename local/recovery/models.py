"""Data models and enums for Recovery Paths (Stage 20 / Candidate E11).

Defines recovery paths, state machine states, action types, context,
and structured recovery decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from local.task_state.models import TaskState


class RecoveryPath(str, Enum):
    """The five canonical recovery families (PLAN.md Section 22 Stage 20)."""

    SEARCH_FALLBACK = "SEARCH_FALLBACK"
    TEST_FAILURE = "TEST_FAILURE"
    BAD_EDIT = "BAD_EDIT"
    TOOL_FAILURE = "TOOL_FAILURE"
    BUDGET_PRESSURE = "BUDGET_PRESSURE"
    NONE = "NONE"


class RecoveryState(str, Enum):
    """Lifecycle state of the recovery controller."""

    NORMAL = "NORMAL"
    FAILURE_CLASSIFIED = "FAILURE_CLASSIFIED"
    NO_PROGRESS_DETECTED = "NO_PROGRESS_DETECTED"
    RECOVERY_SELECTED = "RECOVERY_SELECTED"
    RECOVERY_EXECUTING = "RECOVERY_EXECUTING"
    RECOVERY_VERIFIED = "RECOVERY_VERIFIED"
    RECOVERY_EXHAUSTED = "RECOVERY_EXHAUSTED"
    TERMINAL = "TERMINAL"


class RecoveryActionType(str, Enum):
    """Concrete bounded recovery action types."""

    INSPECT_DIFF = "INSPECT_DIFF"
    INSPECT_STACK = "INSPECT_STACK"
    REVISE_HYPOTHESIS = "REVISE_HYPOTHESIS"
    REPAIR_EDIT = "REPAIR_EDIT"
    REVERT_EDIT = "REVERT_EDIT"
    FALLBACK_SEMANTIC = "FALLBACK_SEMANTIC"
    FALLBACK_EXACT_SEARCH = "FALLBACK_EXACT_SEARCH"
    FALLBACK_TREE_INSPECTION = "FALLBACK_TREE_INSPECTION"
    FALLBACK_GRAPH = "FALLBACK_GRAPH"
    RETRY_TOOL = "RETRY_TOOL"
    USE_ALTERNATE_TOOL = "USE_ALTERNATE_TOOL"
    STOP_EXPLORATION = "STOP_EXPLORATION"
    TARGETED_VALIDATION = "TARGETED_VALIDATION"
    FINAL_REVIEW = "FINAL_REVIEW"
    TERMINATE_PATH = "TERMINATE_PATH"
    NONE = "NONE"


# Maximum string bounds to prevent memory bloat and context explosion
MAX_SUMMARY_LEN = 500
MAX_SNIPPET_LEN = 1000


@dataclass
class RecoveryContext:
    """Structured observable context supplied to RecoveryControllerV1."""

    failure_classification: str | None = None  # from E9 FailureClass
    progress_status: str | None = None  # from E10 ProgressStatus
    no_progress_reason: str | None = None  # from E10 NoProgressReason
    latest_tool_name: str | None = None
    tool_error: str | None = None  # Non-empty only if the tool invocation itself failed
    is_command_syntax_error: bool = False
    latest_command: str = ""
    command_exit_code: int | None = None
    test_result: str | None = None  # "PASSED", "FAILED"
    has_stack_trace: bool = False
    stack_trace_snippet: str = ""
    modified_files: list[str] = field(default_factory=list)
    agent_owned_files: list[str] = field(default_factory=list)  # Files modified by agent
    unrelated_modified_files: list[str] = field(default_factory=list)  # Pre-existing changes
    retrieval_history: list[str] = field(default_factory=list)  # e.g. ["semantic", "exact"]
    source_evidence_sufficient: bool = False
    current_hypothesis: str | None = None
    diff_inspected: bool = False
    remaining_tool_calls: int | None = None
    remaining_time_seconds: float | None = None
    budget_warning_present: bool = False
    recovery_attempts: dict[str, int] = field(default_factory=dict)  # path -> attempt count
    last_recovery_action: str | None = None
    action_produced_new_evidence: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_safe_to_revert(self, file_path: str) -> bool:
        """Determines whether a file can be safely repaired/reverted.

        Only files explicitly created or modified by the agent are safe to touch.
        Pre-existing user/repository changes are strictly preserved.
        """
        clean_path = file_path.replace("\\", "/").strip().lower()
        agent_set = {f.replace("\\", "/").strip().lower() for f in self.agent_owned_files}
        unrelated_set = {f.replace("\\", "/").strip().lower() for f in self.unrelated_modified_files}

        # If it's pre-existing and NOT exclusively agent owned, it is unsafe
        if clean_path in unrelated_set:
            return False
        # Must be in agent-owned set
        return clean_path in agent_set


@dataclass
class RecoveryDecision:
    """Structured decision returned by the recovery controller."""

    state: RecoveryState
    selected_path: RecoveryPath
    action: RecoveryActionType
    target: str = ""  # target file, tool name, or query
    rationale: str = ""
    attempt_number: int = 1
    is_exhausted: bool = False
    evidence_used: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Converts decision to dictionary representation."""
        return {
            "state": self.state.value,
            "selected_path": self.selected_path.value,
            "action": self.action.value,
            "target": self.target,
            "rationale": self.rationale,
            "attempt_number": self.attempt_number,
            "is_exhausted": self.is_exhausted,
            "evidence_used": list(self.evidence_used),
            "timestamp": self.timestamp,
        }

    def format_summary(self) -> str:
        """Produces a compact human-readable summary."""
        evidence_str = "; ".join(self.evidence_used) if self.evidence_used else "None"
        return (
            f"=== Recovery Decision ===\n"
            f"State:     {self.state.value}\n"
            f"Path:      {self.selected_path.value}\n"
            f"Action:    {self.action.value}\n"
            f"Target:    {self.target or 'N/A'}\n"
            f"Attempt:   {self.attempt_number}\n"
            f"Exhausted: {self.is_exhausted}\n"
            f"Rationale: {self.rationale}\n"
            f"Evidence:  {evidence_str}\n"
            f"========================="
        )

    def integrate_into_task_state(self, state: TaskState) -> None:
        """Records recovery decision into TaskState without log bloat or secrets."""
        clean_rationale = f"[{self.selected_path.value} -> {self.action.value}] {self.rationale}"[:MAX_SUMMARY_LEN]
        state.add_evidence(
            observation=f"Recovery decision: {clean_rationale}",
            source="recovery_controller_v1",
            supports_hypothesis=None,
        )
