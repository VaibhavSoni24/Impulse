"""Agent execution adapter for Clean-Copy Evaluation (Stage 28 Phase 6, 22, 26).

Supports:
A. LIVE_EXECUTION: Real competition agent inference when runtime exists.
B. FIXTURE_EXECUTION: Deterministic fake agent for unit, integration, and CI testing.
C. UNAVAILABLE: Explicit status when live Gemma 4 31B execution cannot run on local host.

Adheres strictly to AGENTS.md §2.5 (Zero Fabrication):
Fixture execution is never conflated with live model evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Optional

from local.clean_copy.candidate_loader import LoadedCandidate
from local.clean_copy.models import ExecutionMode
from local.clean_copy.snapshot import CleanRepositorySnapshot
from local.runner.models import ExecutionResult, TaskRecord


def check_live_runtime_available() -> tuple[bool, str]:
    """Checks whether the host has local hardware and vLLM stack for Gemma 4 31B."""
    # Official Gemma 4 31B (gemma-4-31b-it-qat-w4a16-ct) requires 4x NVIDIA L4 GPUs (96 GB VRAM)
    # Check for NVIDIA GPUs
    has_nvidia_smi = False
    try:
        res = subprocess.run(["nvidia-smi"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            has_nvidia_smi = True
    except OSError:
        has_nvidia_smi = False

    if not has_nvidia_smi or os.name == "nt":
        return False, (
            "Local Windows host environment lacks 4x NVIDIA L4 GPUs (96 GB VRAM) "
            "and local vLLM serving stack required to run gemma-4-31b-it-qat-w4a16-ct. "
            "Live execution must be dispatched to Kaggle evaluation container or cloud GPU."
        )

    return False, "Host environment unsupported for local 31B inference."


@dataclass
class FixtureAction:
    """A scripted action performed in the agent workspace for test scenarios."""

    action_type: str  # "write", "edit", "delete", "command"
    path: str = ""
    content: str = ""
    old_content: str = ""
    command: str = ""


@dataclass
class FixtureAgentSpec:
    """Configures deterministic fixture agent behavior (Phase 22)."""

    name: str = "fixture_agent"
    actions: list[FixtureAction] = field(default_factory=list)
    tool_calls: int = 1
    turns: int = 1
    simulate_dirty_pass: bool = False
    untracked_disposable_files: list[tuple[str, str]] = field(default_factory=list)  # (path, content)


class AgentExecutionAdapter:
    """Executes agents inside disposable task workspaces."""

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.FIXTURE,
        fixture_spec: Optional[FixtureAgentSpec] = None,
    ) -> None:
        self.mode = mode
        self.fixture_spec = fixture_spec or FixtureAgentSpec()

    def run(
        self,
        workspace: CleanRepositorySnapshot,
        candidate: LoadedCandidate,
        task: TaskRecord,
    ) -> ExecutionResult:
        """Executes the agent in the isolated workspace."""
        if self.mode == ExecutionMode.UNAVAILABLE:
            return ExecutionResult(
                status="UNAVAILABLE",
                termination_reason="Execution mode explicitly set to UNAVAILABLE.",
                tool_calls_count=0,
                turns_count=0,
            )

        if self.mode == ExecutionMode.LIVE:
            avail, reason = check_live_runtime_available()
            if not avail:
                return ExecutionResult(
                    status="UNAVAILABLE",
                    termination_reason=reason,
                    tool_calls_count=0,
                    turns_count=0,
                    error_message=reason,
                    metrics={"runtime_available": False},
                )
            # If live were available on a cluster, competition container runner would be invoked here
            raise NotImplementedError("Live cluster invocation must be dispatched via competition harness.")

        # Mode == FIXTURE
        return self._run_fixture(workspace, candidate, task)

    def _run_fixture(
        self,
        workspace: CleanRepositorySnapshot,
        candidate: LoadedCandidate,
        task: TaskRecord,
    ) -> ExecutionResult:
        """Executes the deterministic fixture actions in the agent workspace."""
        root = workspace.workspace_dir

        for act in self.fixture_spec.actions:
            if act.action_type == "write":
                p = root / act.path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(act.content, encoding="utf-8")
            elif act.action_type == "edit":
                p = root / act.path
                if p.exists():
                    existing = p.read_text(encoding="utf-8")
                    if act.old_content in existing:
                        updated = existing.replace(act.old_content, act.content)
                        p.write_text(updated, encoding="utf-8")
            elif act.action_type == "delete":
                p = root / act.path
                if p.exists():
                    p.unlink()
            elif act.action_type == "command":
                subprocess.run(
                    act.command,
                    shell=True,
                    cwd=str(root),
                    capture_output=True,
                    check=False,
                )

        # Write untracked disposable files if requested (e.g. scratch.py or run.log)
        for rel_p, content in self.fixture_spec.untracked_disposable_files:
            file_p = root / rel_p
            file_p.parent.mkdir(parents=True, exist_ok=True)
            file_p.write_text(content, encoding="utf-8")

        return ExecutionResult(
            status="COMPLETED",
            termination_reason="Fixture agent completed scripted actions successfully.",
            tool_calls_count=self.fixture_spec.tool_calls,
            turns_count=self.fixture_spec.turns,
            metrics={"fixture_name": self.fixture_spec.name, "execution_mode": "FIXTURE"},
        )
