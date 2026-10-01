"""IMPULSE Stage 42: Free Compute Strategy Subsystem."""

from __future__ import annotations

from local.compute.artifacts import (
    check_disk_budget,
    classify_network_requirement,
    compute_file_sha256,
    create_artifact_transfer_manifest,
    create_return_artifact_manifest,
    is_forbidden_transfer_path,
    scan_for_secrets,
    verify_artifact_transfer_manifest,
    verify_return_artifact_manifest,
)
from local.compute.bootstrap import (
    generate_kaggle_bootstrap_bundle,
    record_bootstrap_execution,
)
from local.compute.capabilities import get_capability_matrix
from local.compute.compatibility import (
    CPU_SUPPORTED_EXPERIMENTS,
    GPU_DEPENDENT_EXPERIMENTS,
    evaluate_experiment_compatibility,
)
from local.compute.errors import (
    ArtifactHashMismatchError,
    ComputeError,
    DiskSpaceInsufficientError,
    HardwareDetectionError,
    IncompatibleEnvironmentError,
    NetworkPolicyViolationError,
    PreflightBlockedError,
    SecretLeakageDetectedError,
)
from local.compute.fingerprint import generate_compute_fingerprint, sanitize_value
from local.compute.hardware import detect_hardware
from local.compute.models import (
    ArtifactTransferItem,
    ArtifactTransferManifest,
    BootstrapMetadata,
    CUDACapability,
    CapabilityItem,
    CapabilityMatrix,
    ComputeFingerprint,
    EnvironmentClass,
    EnvironmentContract,
    EvidenceMode,
    ExecutionMode,
    HardwareProfile,
    NetworkRequirement,
    PreflightCheckResult,
    PreflightStatus,
    ReturnArtifactManifest,
    SoftwareProfile,
    Stage42Decision,
    VerificationStatus,
)
from local.compute.preflight import ComputePreflightAuditor
from local.compute.reporting import (
    PARENT_COMMIT,
    generate_stage42_report,
    write_stage42_reports,
)
from local.compute.software import audit_software

__all__ = [
    "ArtifactHashMismatchError",
    "ArtifactTransferItem",
    "ArtifactTransferManifest",
    "BootstrapMetadata",
    "CUDACapability",
    "CPU_SUPPORTED_EXPERIMENTS",
    "CapabilityItem",
    "CapabilityMatrix",
    "ComputeError",
    "ComputeFingerprint",
    "ComputePreflightAuditor",
    "DiskSpaceInsufficientError",
    "EnvironmentClass",
    "EnvironmentContract",
    "EvidenceMode",
    "ExecutionMode",
    "GPU_DEPENDENT_EXPERIMENTS",
    "HardwareDetectionError",
    "HardwareProfile",
    "IncompatibleEnvironmentError",
    "NetworkPolicyViolationError",
    "NetworkRequirement",
    "PARENT_COMMIT",
    "PreflightBlockedError",
    "PreflightCheckResult",
    "PreflightStatus",
    "ReturnArtifactManifest",
    "SecretLeakageDetectedError",
    "SoftwareProfile",
    "Stage42Decision",
    "VerificationStatus",
    "audit_software",
    "check_disk_budget",
    "classify_network_requirement",
    "compute_file_sha256",
    "create_artifact_transfer_manifest",
    "create_return_artifact_manifest",
    "detect_hardware",
    "evaluate_experiment_compatibility",
    "generate_compute_fingerprint",
    "generate_kaggle_bootstrap_bundle",
    "generate_stage42_report",
    "get_capability_matrix",
    "is_forbidden_transfer_path",
    "record_bootstrap_execution",
    "sanitize_value",
    "scan_for_secrets",
    "verify_artifact_transfer_manifest",
    "verify_return_artifact_manifest",
    "write_stage42_reports",
]
