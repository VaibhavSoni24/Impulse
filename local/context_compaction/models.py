"""Data models and enums for Safe Context Compaction (Stage 25).

Defines:
- CompactionAction: Classification of compaction safety (SAFE_TO_COMPACT, PRESERVE_EXACTLY, etc.)
- ObservationType: Domain classification of observations (FILE_READ, TEST_LOG, etc.)
- HypothesisStatus: Lifecycle states of hypotheses (ACTIVE, SUPERSEDED, CONTRADICTED, RESOLVED)
- FileFingerprint: Content digest and metadata for a file observation
- ChangedFileRecord: Tracking record for file modifications across turns
- CompactedTestLog: Loss-bounded structured test log retaining critical diagnostic lines
- FactObservationSummary: Deduplicated record of repeated repository facts
- HypothesisRecord: Lifecycle tracking record for working hypotheses
- CompactObservation: Deduplicated structured observation with repetition counters
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

MAX_TEXT_PREVIEW_LEN = 500


class CompactionAction(str, Enum):
    """Safety classification for compaction candidates (PLAN.md Stage 25)."""

    SAFE_TO_COMPACT = "SAFE_TO_COMPACT"
    PRESERVE_EXACTLY = "PRESERVE_EXACTLY"
    PRESERVE_WITH_STRUCTURE = "PRESERVE_WITH_STRUCTURE"
    UNKNOWN = "UNKNOWN"


class ObservationType(str, Enum):
    """Categorical type of an observation or tool output."""

    FILE_READ = "FILE_READ"
    COMMAND_OUTPUT = "COMMAND_OUTPUT"
    TEST_LOG = "TEST_LOG"
    REPOSITORY_FACT = "REPOSITORY_FACT"
    HYPOTHESIS_UPDATE = "HYPOTHESIS_UPDATE"
    GENERAL = "GENERAL"


class HypothesisStatus(str, Enum):
    """Lifecycle states of root-cause hypotheses."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    CONTRADICTED = "CONTRADICTED"
    RESOLVED = "RESOLVED"


@dataclass
class FileFingerprint:
    """Content digest and observation metadata for a file."""

    path: str
    sha256: str
    size_bytes: int
    version: int = 1
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChangedFileRecord:
    """Tracking record for modified and inspected files across turns."""

    path: str
    initial_fingerprint: str
    latest_fingerprint: str
    has_changed: bool = False
    edit_count: int = 0
    last_observation: str = ""
    is_relevant: bool = True
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompactedTestLog:
    """Structured, loss-bounded test execution log preserving essential diagnostics."""

    command: str
    exit_code: int
    runner: str  # e.g., "pytest", "unittest", "generic"
    outcome: str  # "PASS", "FAIL", "ERROR", "TIMEOUT"
    failing_tests: list[str] = field(default_factory=list)
    error_lines: list[str] = field(default_factory=list)
    traceback_frames: list[str] = field(default_factory=list)
    file_references: list[str] = field(default_factory=list)
    stderr_summary: str = ""
    passed_count: int = 0
    failed_count: int = 0
    collapsed_boilerplate_lines: int = 0
    preserved_text: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FactObservationSummary:
    """Deduplicated summary of repeated repository facts."""

    fact_key: str
    category: str
    latest_value: str
    observation_count: int = 1
    first_observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    changed_since_previous: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HypothesisRecord:
    """Traceable record of a hypothesis and its lifecycle transitions."""

    hypothesis_id: str
    statement: str
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    transition_reason: str = ""
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class CompactObservation:
    """Bounded, deduplicated observation representation."""

    observation_type: ObservationType
    action: CompactionAction
    fingerprint: str
    source: str = ""
    raw_content_preview: str = ""
    compacted_summary: str = ""
    repetition_count: int = 1
    first_observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_canonical: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["observation_type"] = self.observation_type.value
        d["action"] = self.action.value
        return d
