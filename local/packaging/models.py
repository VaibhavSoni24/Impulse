"""Data models and serialization structures for submission package validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Any, Optional


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    UNAVAILABLE = "UNAVAILABLE"


class CheckSeverity(str, Enum):
    FATAL = "FATAL"
    WARNING = "WARNING"
    INFO = "INFO"


class CheckCategory(str, Enum):
    ARCHIVE_SECURITY = "ARCHIVE_SECURITY"
    SCHEMA_CONFIG = "SCHEMA_CONFIG"
    MODEL_TOOL = "MODEL_TOOL"
    SKILL_MANIFEST = "SKILL_MANIFEST"
    ADAPTER_PEFT = "ADAPTER_PEFT"
    SECRET_HYGIENE = "SECRET_HYGIENE"
    COMPILER_OFFICIAL = "COMPILER_OFFICIAL"
    MUTATION_SAFETY = "MUTATION_SAFETY"


@dataclass(frozen=True)
class CheckResult:
    """Represents the outcome of an individual validation check."""
    check_id: str
    category: CheckCategory
    status: CheckStatus
    severity: CheckSeverity
    target: str
    expected: str
    observed: str
    diagnostic: str
    rule_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category.value,
            "status": self.status.value,
            "severity": self.severity.value,
            "target": self.target,
            "expected": self.expected,
            "observed": self.observed,
            "diagnostic": self.diagnostic,
            "rule_ref": self.rule_ref,
        }


@dataclass
class ArchiveMetadata:
    """Metadata recorded for an inspected ZIP archive."""
    archive_sha256: str
    compressed_size: int
    uncompressed_size: int
    member_count: int
    root_config_path: str
    validator_version: str
    ruleset_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidatorConfig:
    """Configuration options for package validation."""
    strict_mode: bool = False
    max_total_size_bytes: int = 3_221_225_472  # 3 GiB
    check_official_compiler: bool = True


@dataclass
class PackageValidationResult:
    """Aggregate result of a submission package validation run."""
    target_path: str
    target_type: str  # "DIRECTORY" | "ARCHIVE_ZIP"
    overall_valid: bool
    checks: list[CheckResult] = field(default_factory=list)
    archive_metadata: Optional[ArchiveMetadata] = None
    discovered_models: list[str] = field(default_factory=list)
    total_files: int = 0
    total_size_bytes: int = 0
    yaml_files: int = 0
    checks_executed: int = 0
    passed_count: int = 0
    failed_count: int = 0
    warnings_count: int = 0
    skipped_count: int = 0
    unavailable_count: int = 0

    def compute_counts(self, strict_mode: bool = False) -> None:
        """Computes summary counts from checks list."""
        self.checks_executed = len(self.checks)
        self.passed_count = sum(1 for c in self.checks if c.status == CheckStatus.PASS)
        self.failed_count = sum(1 for c in self.checks if c.status == CheckStatus.FAIL)
        self.warnings_count = sum(1 for c in self.checks if c.status == CheckStatus.WARNING)
        self.skipped_count = sum(1 for c in self.checks if c.status == CheckStatus.SKIPPED)
        self.unavailable_count = sum(1 for c in self.checks if c.status == CheckStatus.UNAVAILABLE)

        if self.failed_count > 0:
            self.overall_valid = False
        elif strict_mode and self.warnings_count > 0:
            self.overall_valid = False
        else:
            self.overall_valid = True

    def get_failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    def get_warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.WARNING]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_path": self.target_path,
            "target_type": self.target_type,
            "overall_valid": self.overall_valid,
            "summary": {
                "checks_executed": self.checks_executed,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "warnings": self.warnings_count,
                "skipped": self.skipped_count,
                "unavailable": self.unavailable_count,
            },
            "discovered_models": sorted(self.discovered_models),
            "total_files": self.total_files,
            "total_size_bytes": self.total_size_bytes,
            "yaml_files": self.yaml_files,
            "archive_metadata": self.archive_metadata.to_dict() if self.archive_metadata else None,
            "checks": [c.to_dict() for c in self.checks],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
