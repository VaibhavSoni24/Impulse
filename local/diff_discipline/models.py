"""Data models and enums for Final Diff Discipline and Repository Hygiene (Stage 27).

Defines:
- ArtifactClass: The 14 canonical artifact categories (PLAN.md Stage 27)
- HygieneAction: Recommended action for each artifact (KEEP, REVIEW, REMOVE)
- GitFileStatus: Categorization of Git working tree status (MODIFIED, ADDED, etc.)
- ArtifactFinding: Structured diagnostic record for an inspected artifact
- GitReviewSnapshot: Machine-readable snapshot of git status and diff metrics
- HygieneReport: Comprehensive pre-release cleanliness report
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ArtifactClass(str, Enum):
    """The 14 explicit repository artifact classifications (Stage 27 Phase 3)."""

    REQUIRED_SOURCE = "REQUIRED_SOURCE"
    REQUIRED_CONFIG = "REQUIRED_CONFIG"
    REQUIRED_DOCUMENTATION = "REQUIRED_DOCUMENTATION"
    REQUIRED_TEST_FIXTURE = "REQUIRED_TEST_FIXTURE"
    REQUIRED_EXPERIMENT_ARTIFACT = "REQUIRED_EXPERIMENT_ARTIFACT"
    REQUIRED_REPORT = "REQUIRED_REPORT"
    REQUIRED_BENCHMARK_DATA = "REQUIRED_BENCHMARK_DATA"
    GENERATED_BUT_TRACKED = "GENERATED_BUT_TRACKED"
    IGNORED_LOCAL_ARTIFACT = "IGNORED_LOCAL_ARTIFACT"
    SCRATCH_ARTIFACT = "SCRATCH_ARTIFACT"
    DEBUG_ARTIFACT = "DEBUG_ARTIFACT"
    MACHINE_SPECIFIC_ARTIFACT = "MACHINE_SPECIFIC_ARTIFACT"
    SECRET_OR_CREDENTIAL = "SECRET_OR_CREDENTIAL"
    UNKNOWN = "UNKNOWN"


class HygieneAction(str, Enum):
    """Recommended action for an inspected artifact."""

    KEEP = "KEEP"
    REVIEW = "REVIEW"
    REMOVE = "REMOVE"


class GitFileStatus(str, Enum):
    """Status of a file within the Git working tree."""

    MODIFIED = "MODIFIED"
    ADDED = "ADDED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    UNTRACKED = "UNTRACKED"
    IGNORED = "IGNORED"
    CLEAN = "CLEAN"


@dataclass
class ArtifactFinding:
    """Structured diagnostic finding for an inspected file or line."""

    path: str
    artifact_class: ArtifactClass
    recommended_action: HygieneAction
    reason: str
    confidence: float = 1.0  # 0.0 to 1.0
    is_tracked: bool = False
    is_referenced: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["artifact_class"] = self.artifact_class.value
        d["recommended_action"] = self.recommended_action.value
        return d


@dataclass
class GitReviewSnapshot:
    """Snapshot of Git working tree status and diff statistics."""

    status_short: list[str] = field(default_factory=list)
    diff_stat: str = ""
    diff_name_status: list[tuple[str, str]] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    staged_files: list[str] = field(default_factory=list)
    is_clean: bool = True
    head_commit: str = ""
    branch: str = "main"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HygieneReport:
    """Master repository cleanliness report produced by the review pipeline."""

    findings: list[ArtifactFinding] = field(default_factory=list)
    summary_by_class: dict[str, int] = field(default_factory=dict)
    summary_by_action: dict[str, int] = field(default_factory=dict)
    security_violations: list[str] = field(default_factory=list)
    git_snapshot: GitReviewSnapshot = field(default_factory=GitReviewSnapshot)
    is_clean: bool = True
    requires_test_rerun: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "summary_by_class": dict(self.summary_by_class),
            "summary_by_action": dict(self.summary_by_action),
            "security_violations": list(self.security_violations),
            "git_snapshot": self.git_snapshot.to_dict(),
            "is_clean": self.is_clean,
            "requires_test_rerun": self.requires_test_rerun,
            "timestamp": self.timestamp,
        }
