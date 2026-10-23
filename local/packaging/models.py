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
    ignore_excluded_dev_files: bool = False



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


@dataclass
class PackagedMember:
    """Represents a single member included in the deterministic package."""
    posix_path: str
    source_abs_path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.posix_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass
class PackagerConfig:
    """Configuration options for deterministic submission packaging."""
    source_path: str
    output_path: str = ""
    manifest_path: str = ""
    check_only: bool = False
    strict_mode: bool = False
    force: bool = False
    fixed_timestamp: tuple[int, int, int, int, int, int] = (2026, 1, 1, 0, 0, 0)
    compresslevel: int = 6



@dataclass
class PackagerResult:
    """Outcome of a deterministic packaging run."""
    success: bool
    exit_code: int
    source_path: str
    output_path: Optional[str] = None
    manifest_path: Optional[str] = None
    archive_sha256: Optional[str] = None
    archive_size_bytes: int = 0
    total_files_packaged: int = 0
    total_uncompressed_bytes: int = 0
    candidate_id: Optional[str] = None
    base_model: Optional[str] = None
    agent_name: Optional[str] = None
    source_validation: Optional[PackageValidationResult] = None
    archive_validation: Optional[PackageValidationResult] = None
    excluded_files: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest_data: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "manifest_path": self.manifest_path,
            "archive_sha256": self.archive_sha256,
            "archive_size_bytes": self.archive_size_bytes,
            "total_files_packaged": self.total_files_packaged,
            "total_uncompressed_bytes": self.total_uncompressed_bytes,
            "candidate_id": self.candidate_id,
            "base_model": self.base_model,
            "agent_name": self.agent_name,
            "source_validation": self.source_validation.to_dict() if self.source_validation else None,
            "archive_validation": self.archive_validation.to_dict() if self.archive_validation else None,
            "excluded_files": self.excluded_files,
            "errors": self.errors,
            "warnings": self.warnings,
            "manifest_data": self.manifest_data,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
