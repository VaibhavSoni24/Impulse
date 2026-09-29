"""Data models and schemas for reproducible benchmark dataset splits (Stage 29).

Defines:
- SplitName: DEV, VALIDATION, HELD_OUT
- SplitPolicyType: REPO_DISJOINT, STRATIFIED_COMMIT_ISOLATED
- SourceDatasetMetadata: Source file metadata, hashes, record counts
- SplitInfo: Per-split metadata, task lists, and hashes
- ExclusionRecord: Explicit tracking of excluded source tasks
- SplitManifest: Complete reproducibility manifest
- LeakageAuditReport: Audit findings on cross-split overlap & integrity
- DistributionReport: Statistical summary of split allocations
- SplitLock: Integrity lock for protecting HELD_OUT data
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class SplitName(str, Enum):
    """Canonical benchmark dataset split identifiers."""

    DEV = "dev"
    VALIDATION = "validation"
    HELD_OUT = "held_out"


class SplitPolicyType(str, Enum):
    """Supported split generation policies."""

    REPO_DISJOINT = "repo_disjoint"
    STRATIFIED_COMMIT_ISOLATED = "stratified_commit_isolated"


@dataclass(frozen=True)
class SourceDatasetMetadata:
    """Metadata identifying the immutable source dataset."""

    source_path: str
    source_sha256: str
    record_count: int
    format: str = "jsonl"
    unique_repos: list[str] = field(default_factory=list)
    unique_commits: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "record_count": self.record_count,
            "format": self.format,
            "unique_repos": list(self.unique_repos),
            "unique_commits": self.unique_commits,
        }


@dataclass(frozen=True)
class SplitInfo:
    """Metadata and hashes for a single generated split."""

    name: str
    task_count: int
    task_ids: list[str]
    repo_counts: dict[str, int]
    task_set_sha256: str
    file_sha256: str
    file_relative_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "task_count": self.task_count,
            "task_ids": list(self.task_ids),
            "repo_counts": dict(self.repo_counts),
            "task_set_sha256": self.task_set_sha256,
            "file_sha256": self.file_sha256,
            "file_relative_path": self.file_relative_path,
        }


@dataclass(frozen=True)
class ExclusionRecord:
    """Deterministic record of an excluded source record."""

    instance_id: str
    reason: str
    policy_rule: str
    source_fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "reason": self.reason,
            "policy_rule": self.policy_rule,
            "source_fingerprint": self.source_fingerprint,
        }


@dataclass
class SplitManifest:
    """Complete, reproducible manifest defining benchmark splits."""

    manifest_version: str
    policy_name: str
    policy_version: str
    generator_version: str
    git_commit: str
    created_at: str
    source: SourceDatasetMetadata
    splits: dict[str, SplitInfo]
    exclusions: list[ExclusionRecord] = field(default_factory=list)
    policy_config: dict[str, Any] = field(default_factory=dict)
    manifest_sha256: str = ""

    def to_dict(self, include_hash: bool = True) -> dict[str, Any]:
        res: dict[str, Any] = {
            "manifest_version": self.manifest_version,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "generator_version": self.generator_version,
            "git_commit": self.git_commit,
            "created_at": self.created_at,
            "source": self.source.to_dict(),
            "policy_config": dict(self.policy_config),
            "splits": {k: v.to_dict() for k, v in self.splits.items()},
            "exclusions": [e.to_dict() for e in self.exclusions],
        }
        if include_hash and self.manifest_sha256:
            res["manifest_sha256"] = self.manifest_sha256
        return res


@dataclass
class LeakageAuditReport:
    """Formal audit report evaluating cross-split leakage and completeness."""

    status: str  # "PASS", "WARNING", "FAIL"
    cross_split_task_overlap: list[str]
    cross_split_repo_overlap: dict[str, list[str]]
    cross_split_commit_overlap: dict[str, list[str]]
    duplicate_problem_statements: list[str]
    unaccounted_source_records: list[str]
    checks: dict[str, bool]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": dict(self.checks),
            "cross_split_task_overlap": list(self.cross_split_task_overlap),
            "cross_split_repo_overlap": {k: list(v) for k, v in self.cross_split_repo_overlap.items()},
            "cross_split_commit_overlap": {k: list(v) for k, v in self.cross_split_commit_overlap.items()},
            "duplicate_problem_statements": list(self.duplicate_problem_statements),
            "unaccounted_source_records": list(self.unaccounted_source_records),
            "timestamp": self.timestamp,
        }


@dataclass
class DistributionReport:
    """Descriptive distribution statistics across generated splits."""

    total_records: int
    split_counts: dict[str, int]
    split_proportions: dict[str, float]
    repos_per_split: dict[str, list[str]]
    tasks_per_repo: dict[str, int]
    tasks_per_repo_per_split: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "split_counts": dict(self.split_counts),
            "split_proportions": dict(self.split_proportions),
            "repos_per_split": {k: list(v) for k, v in self.repos_per_split.items()},
            "tasks_per_repo": dict(self.tasks_per_repo),
            "tasks_per_repo_per_split": {k: dict(v) for k, v in self.tasks_per_repo_per_split.items()},
        }


@dataclass
class SplitLock:
    """Protection lock file binding HELD_OUT task identities to manifest."""

    held_out_count: int
    held_out_tasks: list[str]
    held_out_file_sha256: str
    task_set_sha256: str
    manifest_sha256: str
    locked_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "held_out_count": self.held_out_count,
            "held_out_tasks": list(self.held_out_tasks),
            "held_out_file_sha256": self.held_out_file_sha256,
            "task_set_sha256": self.task_set_sha256,
            "manifest_sha256": self.manifest_sha256,
            "locked_at": self.locked_at,
        }
