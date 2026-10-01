"""IMPULSE Stage 43: Candidate Versioning Subsystem."""

from __future__ import annotations

from local.versioning.comparison import MAJOR_DIMENSIONS, CandidateComparator
from local.versioning.errors import (
    DuplicateCandidateError,
    ImmutableCandidateError,
    InvalidStatusTransitionError,
    LineageError,
    MultiDimensionExperimentError,
    SchemaValidationError,
    SecretDetectedInManifestError,
    UnverifiedPromotionError,
    VersioningError,
)
from local.versioning.hashing import (
    compute_canonical_dict_hash,
    compute_directory_manifest_hash,
    compute_file_sha256,
    normalize_machine_paths,
    scan_for_secrets,
)
from local.versioning.importer import import_all_historical_candidates
from local.versioning.models import (
    CandidateManifest,
    CandidateStatus,
    ChangeSummary,
    ComparisonResult,
    CurrentBestPointer,
    EvidenceMode,
    ExperimentDimension,
    LifecycleEvent,
    LifecycleEventType,
    PromotionStatus,
    Stage43Decision,
)
from local.versioning.registry import CandidateRegistry
from local.versioning.reporting import (
    PARENT_COMMIT,
    generate_stage43_report,
    write_stage43_reports,
)
from local.versioning.validation import CandidateValidator

__all__ = [
    "CandidateComparator",
    "CandidateManifest",
    "CandidateRegistry",
    "CandidateStatus",
    "CandidateValidator",
    "ChangeSummary",
    "ComparisonResult",
    "CurrentBestPointer",
    "DuplicateCandidateError",
    "EvidenceMode",
    "ExperimentDimension",
    "ImmutableCandidateError",
    "InvalidStatusTransitionError",
    "LifecycleEvent",
    "LifecycleEventType",
    "LineageError",
    "MAJOR_DIMENSIONS",
    "MultiDimensionExperimentError",
    "PARENT_COMMIT",
    "PromotionStatus",
    "SchemaValidationError",
    "SecretDetectedInManifestError",
    "Stage43Decision",
    "UnverifiedPromotionError",
    "VersioningError",
    "compute_canonical_dict_hash",
    "compute_directory_manifest_hash",
    "compute_file_sha256",
    "generate_stage43_report",
    "import_all_historical_candidates",
    "normalize_machine_paths",
    "scan_for_secrets",
    "write_stage43_reports",
]
