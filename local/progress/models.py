"""Data models and enums for No-Progress Detection (Stage 19 / Candidate E10).

Defines progress states, reasons, cycle snapshots, deterministic fingerprints,
and progress assessment results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from local.task_state.models import TaskState


class ProgressStatus(str, Enum):
    """Overall status of progress across verification cycles (PLAN.md Stage 19)."""

    PROGRESS = "PROGRESS"
    NO_PROGRESS = "NO_PROGRESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class NoProgressReason(str, Enum):
    """Canonical reasons for a lack of progress across cycles."""

    REPEATED_FAILURE = "REPEATED_FAILURE"
    REPEATED_HYPOTHESIS = "REPEATED_HYPOTHESIS"
    REPEATED_EDIT = "REPEATED_EDIT"
    NO_NEW_EVIDENCE = "NO_NEW_EVIDENCE"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


# Bounding limits to prevent memory bloat and context explosion
MAX_FINGERPRINT_INPUT_LEN = 2000
MAX_SUMMARY_LEN = 500


def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing, stripping punctuation, and collapsing whitespace."""
    if not text:
        return ""
    # Truncate if excessively long
    bounded = text[:MAX_FINGERPRINT_INPUT_LEN]
    # Remove dynamic line numbers like ':123:' or ', line 456'
    normalized = re.sub(r":\d+:", "::", bounded)
    normalized = re.sub(r", line \d+", "", normalized)
    # Remove hexadecimal memory addresses like 0x7f9a1b2c3d4e
    normalized = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", normalized)
    # Collapse whitespace and punctuation
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def normalize_code_edit(code: str) -> str:
    """Normalizes code content by stripping per-line whitespace and empty lines."""
    if not code:
        return ""
    bounded = code[:MAX_FINGERPRINT_INPUT_LEN]
    lines = [line.strip() for line in bounded.splitlines() if line.strip()]
    return "\n".join(lines)


def hash_normalized(text: str) -> str:
    """Returns deterministic SHA-256 prefix of normalized text."""
    if not text:
        return "empty"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class CycleSnapshot:
    """Structured representation of a single repair / verification cycle.

    Captures observable inputs without storing unbounded raw logs.
    """

    cycle_id: str | int = ""
    test_command: str = ""
    test_result: str = ""  # "PASSED", "FAILED", or ""
    failure_class: str | None = None  # e.g., one of the 8 canonical FailureClass values
    failure_signature: str = ""  # e.g., failing test name + core exception message
    hypothesis: str | None = None
    modified_files: list[str] = field(default_factory=list)
    edit_content: str = ""  # diff snippet or code modification
    evidence_items: list[str] = field(default_factory=list)
    relevant_source_files: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def failure_fingerprint(self) -> str:
        """Deterministic fingerprint of failure class + normalized failure signature."""
        parts = [
            (self.failure_class or "NONE").upper(),
            normalize_text(self.failure_signature),
            normalize_text(self.test_command),
        ]
        return hash_normalized("|".join(parts))

    def hypothesis_fingerprint(self) -> str:
        """Deterministic fingerprint of the normalized hypothesis."""
        if not self.hypothesis:
            return "no_hypothesis"
        return hash_normalized(normalize_text(self.hypothesis))

    def modified_files_fingerprint(self) -> str:
        """Deterministic fingerprint of sorted modified file paths."""
        if not self.modified_files:
            return "no_files"
        clean_paths = sorted(f.replace("\\", "/").strip().lower() for f in self.modified_files if f.strip())
        return hash_normalized("|".join(clean_paths))

    def relevant_modified_files(self) -> list[str]:
        """Returns the subset of modified files that are relevant source files."""
        if not self.relevant_source_files:
            return list(self.modified_files)
        relevant_set = {f.replace("\\", "/").strip().lower() for f in self.relevant_source_files}
        return [
            f for f in self.modified_files
            if f.replace("\\", "/").strip().lower() in relevant_set
        ]

    def edit_fingerprint(self) -> str:
        """Deterministic fingerprint of normalized code edit."""
        if not self.edit_content:
            return "no_edit"
        return hash_normalized(normalize_code_edit(self.edit_content))

    def evidence_fingerprint(self) -> str:
        """Deterministic fingerprint of normalized diagnostic evidence observations."""
        if not self.evidence_items:
            return "no_evidence"
        normalized_items = sorted(normalize_text(item) for item in self.evidence_items if item.strip())
        return hash_normalized("|".join(normalized_items))


@dataclass
class ProgressAssessment:
    """Structured assessment of progress across cycles."""

    status: ProgressStatus
    reason: NoProgressReason
    consecutive_no_progress_count: int
    threshold: int
    rationale: str
    signals: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Converts assessment record to dictionary."""
        return {
            "status": self.status.value,
            "reason": self.reason.value,
            "consecutive_no_progress_count": self.consecutive_no_progress_count,
            "threshold": self.threshold,
            "rationale": self.rationale,
            "signals": list(self.signals),
            "timestamp": self.timestamp,
        }

    def format_summary(self) -> str:
        """Produces a compact human-readable summary."""
        signals_str = "; ".join(self.signals) if self.signals else "None"
        return (
            f"=== Progress Assessment ===\n"
            f"Status:   {self.status.value}\n"
            f"Reason:   {self.reason.value}\n"
            f"Streak:   {self.consecutive_no_progress_count}/{self.threshold}\n"
            f"Rationale: {self.rationale}\n"
            f"Signals:  {signals_str}\n"
            f"==========================="
        )

    def integrate_into_task_state(self, state: TaskState) -> None:
        """Updates TaskState progress counters and records progress observations cleanly."""
        if self.status == ProgressStatus.NO_PROGRESS:
            state.increment_no_progress()
            clean_rationale = f"[{self.reason.value}] {self.rationale}"[:MAX_SUMMARY_LEN]
            state.add_evidence(
                observation=f"No-progress detected: {clean_rationale}",
                source="no_progress_detector_v1",
                supports_hypothesis=False,
            )
        elif self.status == ProgressStatus.PROGRESS:
            state.reset_no_progress()
