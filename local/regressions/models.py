"""Data models and enums for Stage 45 Failure Regression Suite.

Defines:
- RegressionCategory: Functional domains of discovered failures
- RegressionType: Execution and artifact tiers (FULL_TASK, HARNESS, INFRASTRUCTURE, UNREPRESENTED_BLOCKED)
- RegressionSeverity: Impact level of regression failure
- RegressionStatus: Lifecycle state of a regression case
- RegressionResultStatus: Execution result statuses (PASS, FAIL, BLOCKED, SKIPPED)
- RegressionCase: Typed, versioned regression case specification
- RegressionRunResult: Execution outcome with invariants and provenance
- RegressionManifest: Complete catalog manifest with integrity hashes
- RegressionSuiteSummary: Aggregated execution metrics and results
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class RegressionCategory(str, Enum):
    """Functional domains of discovered failures across IMPULSE development."""

    RETRIEVAL = "RETRIEVAL"
    POLICY = "POLICY"
    RECOVERY = "RECOVERY"
    HYGIENE = "HYGIENE"
    DIFF_DISCIPLINE = "DIFF_DISCIPLINE"
    CALLER_INSPECTION = "CALLER_INSPECTION"
    TESTING = "TESTING"
    SUBMISSION = "SUBMISSION"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    ENVIRONMENT_BLOCKED = "ENVIRONMENT_BLOCKED"


class RegressionType(str, Enum):
    """Execution tier of a regression case (PLAN.md Stage 45 Phase 3)."""

    FULL_TASK_REGRESSION = "FULL_TASK_REGRESSION"
    HARNESS_REGRESSION = "HARNESS_REGRESSION"
    INFRASTRUCTURE_REGRESSION = "INFRASTRUCTURE_REGRESSION"
    UNREPRESENTED_BLOCKED_FAILURE = "UNREPRESENTED_BLOCKED_FAILURE"


class RegressionSeverity(str, Enum):
    """Impact severity of a regression if violated."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RegressionStatus(str, Enum):
    """Lifecycle state of a registered regression case."""

    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    DEPRECATED = "DEPRECATED"


class RegressionResultStatus(str, Enum):
    """Deterministic result status of a regression test execution."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


@dataclass
class RegressionCase:
    """A versioned, candidate-independent regression test case."""

    regression_id: str
    version: str
    title: str
    category: RegressionCategory
    regression_type: RegressionType
    severity: RegressionSeverity
    source_failure_type: str
    description: str
    observed_or_synthetic: str  # "observed", "synthetic", "architectural_invariant", "blocked_environment"
    provenance: dict[str, Any]
    fixture_type: str
    expected_invariants: list[str]
    execution_entrypoint: str
    required_capabilities: list[str]
    status: RegressionStatus
    created_from_stage: str
    created_from_commit: str
    related_candidate_ids: list[str] = field(default_factory=list)
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.signature:
            # Deterministic failure signature for deduplication
            self.signature = f"{self.category.value if isinstance(self.category, Enum) else self.category}:{self.source_failure_type}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "regression_id": self.regression_id,
            "version": self.version,
            "title": self.title,
            "category": self.category.value if isinstance(self.category, Enum) else str(self.category),
            "regression_type": self.regression_type.value if isinstance(self.regression_type, Enum) else str(self.regression_type),
            "severity": self.severity.value if isinstance(self.severity, Enum) else str(self.severity),
            "source_failure_type": self.source_failure_type,
            "description": self.description,
            "observed_or_synthetic": self.observed_or_synthetic,
            "provenance": dict(self.provenance),
            "fixture_type": self.fixture_type,
            "expected_invariants": list(self.expected_invariants),
            "execution_entrypoint": self.execution_entrypoint,
            "required_capabilities": list(self.required_capabilities),
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "created_from_stage": self.created_from_stage,
            "created_from_commit": self.created_from_commit,
            "related_candidate_ids": list(self.related_candidate_ids),
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegressionCase:
        return cls(
            regression_id=str(data["regression_id"]),
            version=str(data.get("version", "1.0.0")),
            title=str(data["title"]),
            category=RegressionCategory(data["category"]),
            regression_type=RegressionType(data["regression_type"]),
            severity=RegressionSeverity(data["severity"]),
            source_failure_type=str(data["source_failure_type"]),
            description=str(data["description"]),
            observed_or_synthetic=str(data["observed_or_synthetic"]),
            provenance=dict(data.get("provenance", {})),
            fixture_type=str(data["fixture_type"]),
            expected_invariants=list(data.get("expected_invariants", [])),
            execution_entrypoint=str(data["execution_entrypoint"]),
            required_capabilities=list(data.get("required_capabilities", [])),
            status=RegressionStatus(data.get("status", RegressionStatus.ACTIVE.value)),
            created_from_stage=str(data.get("created_from_stage", "Stage 45")),
            created_from_commit=str(data.get("created_from_commit", "")),
            related_candidate_ids=list(data.get("related_candidate_ids", [])),
            signature=str(data.get("signature", "")),
        )


@dataclass
class RegressionRunResult:
    """Machine-readable execution result of a single regression test."""

    regression_id: str
    status: RegressionResultStatus
    category: str
    regression_type: str
    expected_invariants: list[str]
    actual_result: str
    provenance: dict[str, Any]
    execution_time_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "regression_id": self.regression_id,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "category": self.category,
            "regression_type": self.regression_type,
            "expected_invariants": list(self.expected_invariants),
            "actual_result": self.actual_result,
            "provenance": dict(self.provenance),
            "execution_time_ms": round(self.execution_time_ms, 2),
            "details": dict(self.details),
            "error_message": self.error_message,
        }


@dataclass
class RegressionManifest:
    """Catalog manifest of all registered regression cases with integrity hash."""

    schema_version: str
    created_at: str
    git_commit: str
    total_cases: int
    cases_by_type: dict[str, int]
    cases_by_category: dict[str, int]
    cases_by_status: dict[str, int]
    cases: list[RegressionCase] = field(default_factory=list)
    manifest_sha256: str = ""

    def compute_sha256(self) -> str:
        """Computes deterministic hash of all cases in canonical order."""
        sorted_cases = sorted([c.to_dict() for c in self.cases], key=lambda x: x["regression_id"])
        canonical_str = json.dumps(sorted_cases, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "git_commit": self.git_commit,
            "total_cases": self.total_cases,
            "cases_by_type": dict(self.cases_by_type),
            "cases_by_category": dict(self.cases_by_category),
            "cases_by_status": dict(self.cases_by_status),
            "manifest_sha256": self.manifest_sha256 or self.compute_sha256(),
            "cases": [c.to_dict() for c in self.cases],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegressionManifest:
        raw_cases = data.get("cases", [])
        cases = [RegressionCase.from_dict(c) for c in raw_cases]
        return cls(
            schema_version=str(data.get("schema_version", "1.0.0")),
            created_at=str(data.get("created_at", "")),
            git_commit=str(data.get("git_commit", "")),
            total_cases=int(data.get("total_cases", len(cases))),
            cases_by_type=dict(data.get("cases_by_type", {})),
            cases_by_category=dict(data.get("cases_by_category", {})),
            cases_by_status=dict(data.get("cases_by_status", {})),
            cases=cases,
            manifest_sha256=str(data.get("manifest_sha256", "")),
        )


@dataclass
class RegressionSuiteSummary:
    """Aggregated execution summary across the regression suite."""

    total_run: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    duration_ms: float = 0.0
    results: list[RegressionRunResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if all executed tests passed or were safely blocked (no unexpected FAIL)."""
        return self.failed == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_run": self.total_run,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "results": [r.to_dict() for r in self.results],
        }
