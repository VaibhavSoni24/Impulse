"""Data models and enums for Stage 46 Stress Test Suite.

Defines:
- StressCategory: 11 required stress test categories + live model tier
- StressType: Execution tier (DETERMINISTIC_COMPONENT, ORCHESTRATION_POLICY, INFRASTRUCTURE, LIVE_MODEL_DRIVEN)
- StressSeverity: Impact severity level
- StressStatus: Lifecycle state (ACTIVE, BLOCKED, DEPRECATED)
- StressResultStatus: Execution result status (PASS, FAIL, BLOCKED, SKIPPED)
- StressCase: Typed specification of a stress scenario
- StressRunResult: Outcome record of a single stress scenario run
- StressManifest: Catalog manifest with cryptographic SHA256 integrity
- StressSuiteSummary: Aggregated metrics across stress suite execution
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class StressCategory(str, Enum):
    """The 11 required stress test families from PLAN.md Stage 46 Section 48."""

    LARGE_REPO = "LARGE_REPO"
    AMBIGUOUS_ISSUE = "AMBIGUOUS_ISSUE"
    MISLEADING_NAMES = "MISLEADING_NAMES"
    MULTIFILE_FIX = "MULTIFILE_FIX"
    HIDDEN_DEPENDENCY = "HIDDEN_DEPENDENCY"
    LONG_LOGS = "LONG_LOGS"
    PREEXISTING_FAILURE = "PREEXISTING_FAILURE"
    NEW_FILE = "NEW_FILE"
    BINARY_FILE = "BINARY_FILE"
    REPEATED_FAILURE = "REPEATED_FAILURE"
    EXPENSIVE_SUITE = "EXPENSIVE_SUITE"
    LIVE_MODEL_EVALUATION = "LIVE_MODEL_EVALUATION"


class StressType(str, Enum):
    """Execution tier of a stress scenario."""

    DETERMINISTIC_COMPONENT = "DETERMINISTIC_COMPONENT"
    ORCHESTRATION_POLICY = "ORCHESTRATION_POLICY"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    LIVE_MODEL_DRIVEN = "LIVE_MODEL_DRIVEN"


class StressSeverity(str, Enum):
    """Impact severity of stress failure."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class StressStatus(str, Enum):
    """Lifecycle state of a stress case."""

    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    DEPRECATED = "DEPRECATED"


class StressResultStatus(str, Enum):
    """Outcome status of stress execution."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


@dataclass
class StressCase:
    """A versioned, candidate-independent stress test specification."""

    stress_id: str
    version: str
    title: str
    category: StressCategory
    stress_type: StressType
    severity: StressSeverity
    scenario_description: str
    fixture_type: str
    source_requirement: str
    provenance: dict[str, Any]
    expected_invariants: list[str]
    execution_entrypoint: str
    resource_limits: dict[str, Any]
    related_regression_ids: list[str]
    testing_tier: str  # "deterministic_component", "orchestration_policy", "live_model_driven"
    status: StressStatus
    terminal_status: str = "PASS"
    blocked_reason: str = ""
    created_from_stage: str = "Stage 46"
    created_from_commit: str = "9b137adcf25f90ba264f114980852afdd1bfeed0"
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.signature:
            cat_str = self.category.value if isinstance(self.category, Enum) else str(self.category)
            self.signature = f"{cat_str}:{self.stress_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stress_id": self.stress_id,
            "version": self.version,
            "title": self.title,
            "category": self.category.value if isinstance(self.category, Enum) else str(self.category),
            "stress_type": self.stress_type.value if isinstance(self.stress_type, Enum) else str(self.stress_type),
            "severity": self.severity.value if isinstance(self.severity, Enum) else str(self.severity),
            "scenario_description": self.scenario_description,
            "fixture_type": self.fixture_type,
            "source_requirement": self.source_requirement,
            "provenance": dict(self.provenance),
            "expected_invariants": list(self.expected_invariants),
            "execution_entrypoint": self.execution_entrypoint,
            "resource_limits": dict(self.resource_limits),
            "related_regression_ids": list(self.related_regression_ids),
            "testing_tier": self.testing_tier,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "terminal_status": self.terminal_status,
            "blocked_reason": self.blocked_reason,
            "created_from_stage": self.created_from_stage,
            "created_from_commit": self.created_from_commit,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StressCase:
        category = StressCategory(data["category"])
        stress_type = StressType(data["stress_type"])
        severity = StressSeverity(data["severity"])
        status = StressStatus(data["status"])
        return cls(
            stress_id=data["stress_id"],
            version=data["version"],
            title=data["title"],
            category=category,
            stress_type=stress_type,
            severity=severity,
            scenario_description=data["scenario_description"],
            fixture_type=data["fixture_type"],
            source_requirement=data["source_requirement"],
            provenance=data.get("provenance", {}),
            expected_invariants=data.get("expected_invariants", []),
            execution_entrypoint=data["execution_entrypoint"],
            resource_limits=data.get("resource_limits", {}),
            related_regression_ids=data.get("related_regression_ids", []),
            testing_tier=data.get("testing_tier", "deterministic_component"),
            status=status,
            terminal_status=data.get("terminal_status", "PASS"),
            blocked_reason=data.get("blocked_reason", ""),
            created_from_stage=data.get("created_from_stage", "Stage 46"),
            created_from_commit=data.get("created_from_commit", ""),
            signature=data.get("signature", ""),
        )


@dataclass
class StressRunResult:
    """Execution telemetry and evaluation outcome for a single stress case."""

    stress_id: str
    status: StressResultStatus
    category: str
    stress_type: str
    testing_tier: str
    expected_invariants: list[str]
    actual_result: str
    provenance: dict[str, Any]
    execution_time_ms: float
    fixture_metrics: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stress_id": self.stress_id,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "category": self.category,
            "stress_type": self.stress_type,
            "testing_tier": self.testing_tier,
            "expected_invariants": list(self.expected_invariants),
            "actual_result": self.actual_result,
            "provenance": dict(self.provenance),
            "execution_time_ms": self.execution_time_ms,
            "fixture_metrics": dict(self.fixture_metrics),
            "details": dict(self.details),
            "error_message": self.error_message,
        }


@dataclass
class StressManifest:
    """Stress suite manifest tracking the catalog and cryptographic hash."""

    schema_version: str
    created_at_utc: str
    commit_hash: str
    total_cases: int
    cases: list[dict[str, Any]]
    manifest_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.manifest_sha256:
            self.manifest_sha256 = self.compute_sha256()

    def compute_sha256(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "commit_hash": self.commit_hash,
            "total_cases": self.total_cases,
            "cases": sorted(self.cases, key=lambda c: c["stress_id"]),
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at_utc": self.created_at_utc,
            "commit_hash": self.commit_hash,
            "total_cases": self.total_cases,
            "manifest_sha256": self.manifest_sha256,
            "cases": self.cases,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StressManifest:
        return cls(
            schema_version=data["schema_version"],
            created_at_utc=data["created_at_utc"],
            commit_hash=data["commit_hash"],
            total_cases=data["total_cases"],
            cases=data["cases"],
            manifest_sha256=data.get("manifest_sha256", ""),
        )


@dataclass
class StressSuiteSummary:
    """Aggregated outcome of running the full stress test suite."""

    schema_version: str
    total_registered: int
    total_attempted: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    deterministic_component_count: int
    orchestration_policy_count: int
    live_model_driven_count: int
    live_scenarios_executed: int
    live_scenarios_blocked: int
    total_elapsed_ms: float
    results: list[StressRunResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "total_registered": self.total_registered,
            "total_attempted": self.total_attempted,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "deterministic_component_count": self.deterministic_component_count,
            "orchestration_policy_count": self.orchestration_policy_count,
            "live_model_driven_count": self.live_model_driven_count,
            "live_scenarios_executed": self.live_scenarios_executed,
            "live_scenarios_blocked": self.live_scenarios_blocked,
            "total_elapsed_ms": self.total_elapsed_ms,
            "results": [r.to_dict() for r in self.results],
        }
