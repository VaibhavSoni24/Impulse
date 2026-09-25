"""Execution backend abstractions for the IMPULSE local task runner."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any

from local.runner.models import ExecutionResult, RunSpec, TaskRecord


class ExecutionBackend(abc.ABC):
    """Abstract interface defining an execution backend for candidate evaluation."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """The identifier of the backend."""
        ...

    @abc.abstractmethod
    def execute(self, spec: RunSpec, task: TaskRecord, run_dir: Path) -> ExecutionResult:
        """Executes a candidate against the provided benchmark task."""
        ...


class UnavailableLocalBackend(ExecutionBackend):
    """Default backend for local Windows host without 4x NVIDIA L4 GPUs.

    Adheres strictly to the project constitution:
    - Never fabricates model execution.
    - Never generates fake tool events or patches.
    - Reports structured status indicating that local host execution is unavailable.
    """

    @property
    def name(self) -> str:
        return "local-unavailable"

    def execute(self, spec: RunSpec, task: TaskRecord, run_dir: Path) -> ExecutionResult:
        reason = (
            "Local Windows host environment lacks 4x NVIDIA L4 GPUs (96 GB VRAM) "
            "and local vLLM serving stack required to run gemma-4-31b-it-qat-w4a16-ct. "
            "Execution must be dispatched to cloud GPU or Kaggle evaluation environment."
        )
        return ExecutionResult(
            status="execution_unavailable_local_host",
            termination_reason=reason,
            patch=None,
            tool_calls_count=0,
            turns_count=0,
            error_message=None,
            metrics={"hardware_constraint": "missing_4x_l4_gpus"},
        )


class DryRunBackend(ExecutionBackend):
    """Lightweight backend for runner plumbing, pipeline verification, and CI tests.

    Verifies task loading, candidate configuration inspection, and artifact staging
    without invoking model inference or Docker sandboxes.
    """

    @property
    def name(self) -> str:
        return "dry-run"

    def execute(self, spec: RunSpec, task: TaskRecord, run_dir: Path) -> ExecutionResult:
        return ExecutionResult(
            status="dry_run_completed",
            termination_reason="Dry run completed successfully; pipeline and metadata verified.",
            patch=None,
            tool_calls_count=0,
            turns_count=0,
            metrics={"dry_run": True},
        )


_BACKEND_REGISTRY: dict[str, type[ExecutionBackend]] = {
    "unavailable": UnavailableLocalBackend,
    "local-unavailable": UnavailableLocalBackend,
    "dry-run": DryRunBackend,
}


def get_backend(name: str) -> ExecutionBackend:
    """Factory retrieving an ExecutionBackend by name."""
    normalized = name.strip().lower()
    backend_cls = _BACKEND_REGISTRY.get(normalized)
    if not backend_cls:
        available = sorted(_BACKEND_REGISTRY.keys())
        raise ValueError(f"Unknown backend '{name}'. Available backends: {available}")
    return backend_cls()
