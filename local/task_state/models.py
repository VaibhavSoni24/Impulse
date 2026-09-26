"""Structured task state data models and invariants for IMPULSE (Stage 11)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any

MAX_COLLECTION_SIZE = 50


@dataclass
class RepositoryFact:
    """Discovered architectural, framework, or convention fact."""

    category: str
    fact: str
    source: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateLocation:
    """Suspect file, module, symbol, or line identified during investigation."""

    path: str
    symbol: str = ""
    line_number: int | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceItem:
    """Concrete empirical observation supporting or refuting a hypothesis."""

    observation: str
    source_command_or_file: str = ""
    supports_hypothesis: bool | None = None  # True=supports, False=refutes, None=neutral
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EditRecord:
    """Record of a source modification made to the workspace."""

    path: str
    description: str
    rationale: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TestRecord:
    """Record of a targeted test command execution."""

    command: str
    outcome: str  # "PASS", "FAIL", "ERROR", "TIMEOUT"
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailureRecord:
    """Record of a failure diagnosis encountered during reproduction or testing."""

    failure_type: str
    description: str
    traceback_snippet: str = ""
    resolved: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FinalReviewRecord:
    """Pre-submission verification checklist."""

    diff_inspected: bool = False
    scratch_files_removed: bool = False
    intended_files_only: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskState:
    """Authoritative structured task state representation (PLAN.md Section 13).

    Maintains continuity across turns and prevents repeated exploration.
    """

    summary: str = ""
    repository_facts: list[RepositoryFact] = field(default_factory=list)
    candidates: list[CandidateLocation] = field(default_factory=list)
    hypothesis: str | None = None
    evidence: list[EvidenceItem] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    edits: list[EditRecord] = field(default_factory=list)
    tests: list[TestRecord] = field(default_factory=list)
    failures: list[FailureRecord] = field(default_factory=list)
    no_progress_count: int = 0
    final_review: FinalReviewRecord = field(default_factory=FinalReviewRecord)

    def validate(self) -> None:
        """Validates all structural invariants."""
        if not isinstance(self.no_progress_count, int):
            raise TypeError("no_progress_count must be an integer.")
        if self.no_progress_count < 0:
            raise ValueError(f"no_progress_count cannot be negative: {self.no_progress_count}")
        if not isinstance(self.summary, str):
            raise TypeError("summary must be a string.")
        if self.hypothesis is not None and not isinstance(self.hypothesis, str):
            raise TypeError("hypothesis must be a string or None.")
        if not isinstance(self.plan, list) or not all(isinstance(p, str) for p in self.plan):
            raise TypeError("plan must be a list of strings.")

    def add_repository_fact(self, category: str, fact: str, source: str = "") -> None:
        """Adds a repository fact with capacity bound."""
        self.repository_facts.append(RepositoryFact(category=category, fact=fact, source=source))
        if len(self.repository_facts) > MAX_COLLECTION_SIZE:
            self.repository_facts.pop(0)

    def add_candidate(self, path: str, symbol: str = "", line_number: int | None = None, rationale: str = "") -> None:
        """Adds a candidate location with capacity bound."""
        self.candidates.append(CandidateLocation(path=path, symbol=symbol, line_number=line_number, rationale=rationale))
        if len(self.candidates) > MAX_COLLECTION_SIZE:
            self.candidates.pop(0)

    def set_hypothesis(self, hypothesis: str | None) -> None:
        """Sets the working root cause hypothesis."""
        self.hypothesis = hypothesis

    def add_evidence(self, observation: str, source: str = "", supports_hypothesis: bool | None = None) -> None:
        """Adds an evidence observation."""
        self.evidence.append(EvidenceItem(observation=observation, source_command_or_file=source, supports_hypothesis=supports_hypothesis))
        if len(self.evidence) > MAX_COLLECTION_SIZE:
            self.evidence.pop(0)

    def set_plan(self, steps: list[str]) -> None:
        """Sets the tactical plan steps."""
        self.plan = list(steps)

    def add_edit(self, path: str, description: str, rationale: str = "") -> None:
        """Logs a source code modification."""
        self.edits.append(EditRecord(path=path, description=description, rationale=rationale))
        if len(self.edits) > MAX_COLLECTION_SIZE:
            self.edits.pop(0)

    def add_test(self, command: str, outcome: str, summary: str = "") -> None:
        """Logs a test execution result."""
        # Sanitize summary to avoid multi-thousand character bloating
        clean_summary = summary[:500] if summary else ""
        self.tests.append(TestRecord(command=command, outcome=outcome, summary=clean_summary))
        if len(self.tests) > MAX_COLLECTION_SIZE:
            self.tests.pop(0)

    def add_failure(self, failure_type: str, description: str, traceback_snippet: str = "", resolved: bool = False) -> None:
        """Logs a failure diagnostic record."""
        clean_tb = traceback_snippet[:1000] if traceback_snippet else ""
        self.failures.append(FailureRecord(failure_type=failure_type, description=description, traceback_snippet=clean_tb, resolved=resolved))
        if len(self.failures) > MAX_COLLECTION_SIZE:
            self.failures.pop(0)

    def increment_no_progress(self) -> int:
        """Increments no-progress counter and returns updated count."""
        self.no_progress_count += 1
        return self.no_progress_count

    def reset_no_progress(self) -> None:
        """Resets no-progress counter upon constructive action."""
        self.no_progress_count = 0

    def update_final_review(
        self,
        diff_inspected: bool | None = None,
        scratch_files_removed: bool | None = None,
        intended_files_only: bool | None = None,
        notes: str | None = None,
    ) -> None:
        """Updates pre-submission review fields."""
        if diff_inspected is not None:
            self.final_review.diff_inspected = diff_inspected
        if scratch_files_removed is not None:
            self.final_review.scratch_files_removed = scratch_files_removed
        if intended_files_only is not None:
            self.final_review.intended_files_only = intended_files_only
        if notes is not None:
            self.final_review.notes = notes

    def to_dict(self) -> dict[str, Any]:
        """Serializes TaskState to a JSON-safe dictionary."""
        self.validate()
        return {
            "summary": self.summary,
            "repository_facts": [f.to_dict() for f in self.repository_facts],
            "candidates": [c.to_dict() for c in self.candidates],
            "hypothesis": self.hypothesis,
            "evidence": [e.to_dict() for e in self.evidence],
            "plan": list(self.plan),
            "edits": [ed.to_dict() for ed in self.edits],
            "tests": [t.to_dict() for t in self.tests],
            "failures": [f.to_dict() for f in self.failures],
            "no_progress_count": self.no_progress_count,
            "final_review": self.final_review.to_dict(),
        }

    def to_json(self, indent: int | None = 2) -> str:
        """Serializes TaskState to a deterministic JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskState:
        """Deserializes a dictionary into a validated TaskState instance."""
        state = cls(
            summary=data.get("summary", ""),
            repository_facts=[RepositoryFact(**f) for f in data.get("repository_facts", [])],
            candidates=[CandidateLocation(**c) for c in data.get("candidates", [])],
            hypothesis=data.get("hypothesis"),
            evidence=[EvidenceItem(**e) for e in data.get("evidence", [])],
            plan=list(data.get("plan", [])),
            edits=[EditRecord(**ed) for ed in data.get("edits", [])],
            tests=[TestRecord(**t) for t in data.get("tests", [])],
            failures=[FailureRecord(**f) for f in data.get("failures", [])],
            no_progress_count=int(data.get("no_progress_count", 0)),
            final_review=FinalReviewRecord(**data.get("final_review", {})),
        )
        state.validate()
        return state

    @classmethod
    def from_json(cls, json_str: str) -> TaskState:
        """Deserializes a JSON string into a validated TaskState instance."""
        data = json.loads(json_str)
        return cls.from_dict(data)
