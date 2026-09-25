"""Data models and schemas for the IMPULSE local task runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskRecord:
    """Represents a benchmark task record extracted from tasks.jsonl."""

    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    hints_text: str = ""
    created_at: str = ""
    has_test_patch: bool = False

    def to_metadata_dict(self) -> dict[str, Any]:
        """Returns non-sensitive metadata for logging and reproduction.

        Excludes golden ground-truth patches during execution preparation.
        """
        return {
            "instance_id": self.instance_id,
            "repo": self.repo,
            "base_commit": self.base_commit,
            "problem_statement_chars": len(self.problem_statement),
            "hints_text_chars": len(self.hints_text),
            "created_at": self.created_at,
            "has_test_patch": self.has_test_patch,
        }


@dataclass
class RunSpec:
    """Specification and configuration parameters for a candidate task execution."""

    task_id: str
    candidate_id: str
    candidate_dir: Path
    output_dir: Path = Path("runs")
    timeout_seconds: int | None = None
    tool_calls_budget: int | None = None
    backend_name: str = "unavailable"
    extra_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Outcome of an execution backend attempt."""

    status: str
    termination_reason: str
    patch: str | None = None
    tool_calls_count: int = 0
    turns_count: int = 0
    error_message: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunMetadata:
    """Authoritative machine-readable execution record written to run.json."""

    run_id: str
    candidate_id: str
    task_id: str
    model_id: str
    prompt_id: str
    execution_backend: str
    status: str
    termination_reason: str
    start_time: str
    end_time: str
    elapsed_time_seconds: float
    timeout_seconds: int | None
    tool_calls_budget: int | None
    git_commit: str | None = None
    tool_calls_count: int = 0
    turns_count: int = 0
    error_message: str | None = None
    patch_generated: bool = False
    run_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
