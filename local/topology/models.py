"""Data models for Multi-Agent Topology Experiments (Stage 24).

Defines:
- TopologyID enum (M0, M1, M2, M3, M4, M5)
- SpecialistName enum (scout, debugger, reviewer)
- SelectionStatus enum (UNRESOLVED, SELECTED, REJECTED)
- TopologyDefinition dataclass
- TaskRunRecord dataclass (per-run result tracking)
- TopologyAggregateMetrics dataclass (aggregated metrics across runs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TopologyID(str, Enum):
    """Canonical Stage 24 topology identifiers."""

    M0 = "M0"  # Root only
    M1 = "M1"  # Root + Scout
    M2 = "M2"  # Root + Debugger
    M3 = "M3"  # Root + Reviewer
    M4 = "M4"  # Root + Scout + Debugger
    M5 = "M5"  # Root + Scout + Debugger + Reviewer


class SpecialistName(str, Enum):
    """Canonical specialist names."""

    SCOUT = "scout"
    DEBUGGER = "debugger"
    REVIEWER = "reviewer"


class SelectionStatus(str, Enum):
    """Topology evaluation selection status."""

    UNRESOLVED = "UNRESOLVED"  # No benchmark evidence available; selection cannot be made
    SELECTED = "SELECTED"      # Promoted based on validated and held-out evidence
    REJECTED = "REJECTED"      # Measured and failed selection criteria


@dataclass(frozen=True)
class TopologyDefinition:
    """Immutable specification of a candidate topology."""

    topology_id: str
    name: str
    description: str
    specialists: tuple[str, ...]
    root_model: str = "gemma-4-31b-it-qat-w4a16-ct"
    root_tools: tuple[str, ...] = (
        "run_command",
        "read_file",
        "edit_file",
        "write_file",
        "get_status",
        "submit_patch",
        "search_similar_code",
        "get_code_neighbors",
        "get_code_subgraph",
    )
    skills: tuple[str, ...] = (
        "skills/test_strategy",
        "skills/repo_triage",
    )

    @property
    def specialist_count(self) -> int:
        return len(self.specialists)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_id": self.topology_id,
            "name": self.name,
            "description": self.description,
            "specialists": list(self.specialists),
            "specialist_count": self.specialist_count,
            "root_model": self.root_model,
            "root_tools": list(self.root_tools),
            "skills": list(self.skills),
        }


@dataclass
class TaskRunRecord:
    """Normalized record of a single task execution under a specific topology."""

    topology_id: str
    task_id: str
    success: bool = False
    elapsed_seconds: float = 0.0
    turns: int = 0
    tool_calls: int = 0
    root_turns: int = 0
    specialist_calls: dict[str, int] = field(default_factory=dict)
    failure_class: str | None = None
    recovery_triggered: bool = False
    recovery_success: bool = False
    patch_lines: int = 0
    files_changed: int = 0
    final_review_status: str | None = None
    termination_reason: str = "COMPLETED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_id": self.topology_id,
            "task_id": self.task_id,
            "success": self.success,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "root_turns": self.root_turns,
            "specialist_calls": dict(self.specialist_calls),
            "failure_class": self.failure_class,
            "recovery_triggered": self.recovery_triggered,
            "recovery_success": self.recovery_success,
            "patch_lines": self.patch_lines,
            "files_changed": self.files_changed,
            "final_review_status": self.final_review_status,
            "termination_reason": self.termination_reason,
        }


@dataclass
class TopologyAggregateMetrics:
    """Aggregated evaluation metrics for a topology."""

    topology_id: str
    total_tasks: int = 0
    resolved_tasks: int = 0
    failed_tasks: int = 0
    pass_rate: float | None = None
    avg_runtime_seconds: float | None = None
    avg_turns: float | None = None
    avg_tool_calls: float | None = None
    avg_specialist_calls: float | None = None
    total_specialist_calls: int = 0
    recovery_attempt_count: int = 0
    recovery_success_count: int = 0
    recovery_success_rate: float | None = None
    evidence_status: str = "UNEXECUTED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_id": self.topology_id,
            "total_tasks": self.total_tasks,
            "resolved_tasks": self.resolved_tasks,
            "failed_tasks": self.failed_tasks,
            "pass_rate": round(self.pass_rate, 4) if self.pass_rate is not None else None,
            "avg_runtime_seconds": round(self.avg_runtime_seconds, 2) if self.avg_runtime_seconds is not None else None,
            "avg_turns": round(self.avg_turns, 2) if self.avg_turns is not None else None,
            "avg_tool_calls": round(self.avg_tool_calls, 2) if self.avg_tool_calls is not None else None,
            "avg_specialist_calls": round(self.avg_specialist_calls, 2) if self.avg_specialist_calls is not None else None,
            "total_specialist_calls": self.total_specialist_calls,
            "recovery_attempt_count": self.recovery_attempt_count,
            "recovery_success_count": self.recovery_success_count,
            "recovery_success_rate": round(self.recovery_success_rate, 4) if self.recovery_success_rate is not None else None,
            "evidence_status": self.evidence_status,
        }
