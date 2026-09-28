"""Data models, enums, and schemas for Clean-Copy Evaluation (Stage 28).

Defines:
- FailureStage: Specific pipeline stage where failure occurred
- EvaluatorFailureClass: Explicit taxonomy for evaluation infrastructure issues
- ExecutionMode: LIVE, FIXTURE, or UNAVAILABLE
- WorkspaceCreationMethod: WORKTREE, CLONE, or EXPORT
- PatchBundle: Complete self-contained captured diff payload
- EvaluationRunRecord: Authoritative Stage 28 clean-copy evaluation result
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Optional


class FailureStage(str, Enum):
    """Pipeline stage where evaluation failed (Phase 13)."""

    PREPARE = "PREPARE"
    CANDIDATE_LOAD = "CANDIDATE_LOAD"
    AGENT_EXECUTION = "AGENT_EXECUTION"
    PATCH_EXTRACTION = "PATCH_EXTRACTION"
    PATCH_APPLICATION = "PATCH_APPLICATION"
    VERIFICATION = "VERIFICATION"
    CLEANUP = "CLEANUP"
    UNKNOWN = "UNKNOWN"


class EvaluatorFailureClass(str, Enum):
    """Deterministic classification of evaluator infrastructure failures (Phase 14)."""

    BASELINE_NOT_CLEAN = "BASELINE_NOT_CLEAN"
    BASELINE_NOT_FOUND = "BASELINE_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    CANDIDATE_INVALID = "CANDIDATE_INVALID"
    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    AGENT_START_FAILURE = "AGENT_START_FAILURE"
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    PATCH_EXTRACTION_FAILURE = "PATCH_EXTRACTION_FAILURE"
    PATCH_APPLY_CONFLICT = "PATCH_APPLY_CONFLICT"
    PATCH_EQUIVALENCE_FAILURE = "PATCH_EQUIVALENCE_FAILURE"
    VERIFICATION_COMMAND_FAILURE = "VERIFICATION_COMMAND_FAILURE"
    VERIFICATION_TEST_FAILURE = "VERIFICATION_TEST_FAILURE"
    CLEANUP_FAILURE = "CLEANUP_FAILURE"
    UNKNOWN = "UNKNOWN"


class ExecutionMode(str, Enum):
    """Mode of agent execution."""

    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    UNAVAILABLE = "UNAVAILABLE"


class WorkspaceCreationMethod(str, Enum):
    """Mechanism used to create isolated clean repository snapshots."""

    WORKTREE = "WORKTREE"
    CLONE = "CLONE"
    EXPORT = "EXPORT"


@dataclass
class PatchBundle:
    """Deterministic representation of captured patch and affected files (Phase 9)."""

    run_id: str
    task_id: str
    candidate_id: str
    baseline_commit: str
    patch_format_version: str = "v1"
    tracked_diff: str = ""
    new_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    patch_sha256: str = ""
    extraction_status: str = "OK"  # "OK", "EMPTY", "FAILED"

    def compute_sha256(self) -> str:
        """Computes deterministic SHA-256 digest of the patch text."""
        h = hashlib.sha256(self.tracked_diff.encode("utf-8")).hexdigest()
        self.patch_sha256 = h
        return h

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationRunRecord:
    """Master record for a clean-copy evaluation run (Phase 13)."""

    run_id: str
    task_id: str
    candidate_id: str
    baseline_commit: str
    candidate_config_sha256: str
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: str = ""
    execution_status: str = "PENDING"  # "COMPLETED", "FAILED", "UNAVAILABLE", "TIMEOUT"
    agent_status: str = ""
    patch_extraction_status: str = ""  # "EXTRACTED", "NO_CHANGES", "FAILED"
    patch_apply_status: str = ""  # "APPLIED", "FAILED", "SKIPPED"
    verification_status: str = ""  # "PASSED", "FAILED", "SKIPPED", "ERROR"
    success: bool = False
    termination_reason: str = ""
    patch_sha256: str = ""
    files_changed: int = 0
    patch_lines: int = 0
    tool_calls: int = 0
    turns: int = 0
    elapsed_seconds: float = 0.0
    failure_class: Optional[EvaluatorFailureClass] = None
    failure_stage: Optional[FailureStage] = None
    workspace_isolated: bool = True
    clean_copy_verified: bool = False
    verification_command: str = ""
    verification_output: str = ""
    manifest_hash: str = ""

    def compute_manifest_hash(self) -> str:
        """Generates a deterministic hash representing this evaluation outcome."""
        payload = {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "candidate_id": self.candidate_id,
            "baseline_commit": self.baseline_commit,
            "candidate_config_sha256": self.candidate_config_sha256,
            "patch_sha256": self.patch_sha256,
            "success": self.success,
            "verification_status": self.verification_status,
            "clean_copy_verified": self.clean_copy_verified,
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.manifest_hash = hashlib.sha256(encoded).hexdigest()
        return self.manifest_hash

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.failure_class:
            d["failure_class"] = self.failure_class.value
        if self.failure_stage:
            d["failure_stage"] = self.failure_stage.value
        return d
