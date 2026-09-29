"""Reproducible benchmark dataset splits package (Stage 29).

Exports:
- SplitName, SplitPolicyType, SplitManifest, LeakageAuditReport, DistributionReport, SplitLock
- SplitGenerator
- validate_split_leakage
- load_manifest, save_manifest, verify_manifest_integrity, detect_source_change
- create_held_out_lock, verify_held_out_lock, is_held_out_task
- compute_canonical_task_set_hash, compute_file_sha256, compute_task_fingerprint
"""

from benchmark.splits.generator import SplitGenerator
from benchmark.splits.hashing import (
    compute_canonical_task_set_hash,
    compute_file_sha256,
    compute_manifest_sha256,
    compute_task_fingerprint,
)
from benchmark.splits.held_out_lock import (
    create_held_out_lock,
    is_held_out_task,
    load_held_out_lock,
    verify_held_out_lock,
)
from benchmark.splits.leakage import LeakageValidationError, validate_split_leakage
from benchmark.splits.manifests import (
    detect_source_change,
    load_manifest,
    save_manifest,
    verify_manifest_integrity,
)
from benchmark.splits.models import (
    DistributionReport,
    ExclusionRecord,
    LeakageAuditReport,
    SourceDatasetMetadata,
    SplitInfo,
    SplitLock,
    SplitManifest,
    SplitName,
    SplitPolicyType,
)

__all__ = [
    "SplitName",
    "SplitPolicyType",
    "SourceDatasetMetadata",
    "SplitInfo",
    "ExclusionRecord",
    "SplitManifest",
    "LeakageAuditReport",
    "DistributionReport",
    "SplitLock",
    "SplitGenerator",
    "validate_split_leakage",
    "LeakageValidationError",
    "compute_canonical_task_set_hash",
    "compute_file_sha256",
    "compute_manifest_sha256",
    "compute_task_fingerprint",
    "create_held_out_lock",
    "verify_held_out_lock",
    "is_held_out_task",
    "load_held_out_lock",
    "load_manifest",
    "save_manifest",
    "verify_manifest_integrity",
    "detect_source_change",
]
