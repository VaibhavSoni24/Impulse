"""Models, Enums, and Dataclasses for Stage 42 Free Compute Strategy.

Separates:
- COMPUTE ENVIRONMENT
- EXPERIMENT CONFIGURATION
- RESULTS

Ensures experiment configuration remains invariant across execution environments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class EnvironmentClass(str, Enum):
    """Execution environment classifications."""
    LOCAL_CPU = "LOCAL_CPU"
    LOCAL_GPU = "LOCAL_GPU"
    KAGGLE_FREE_GPU = "KAGGLE_FREE_GPU"
    EXTERNAL_LINUX_GPU = "EXTERNAL_LINUX_GPU"
    UNKNOWN = "UNKNOWN"


class CUDACapability(str, Enum):
    """CUDA and GPU capability classifications."""
    NO_CUDA_GPU = "NO_CUDA_GPU"
    CUDA_AVAILABLE = "CUDA_AVAILABLE"
    CUDA_UNAVAILABLE = "CUDA_UNAVAILABLE"


class VerificationStatus(str, Enum):
    """Verification truth classifications."""
    SUPPORTED_BY_DESIGN = "SUPPORTED_BY_DESIGN"
    ACTUALLY_VERIFIED = "ACTUALLY_VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    BLOCKED = "BLOCKED"


class PreflightStatus(str, Enum):
    """Preflight execution gating statuses."""
    READY = "READY"
    BLOCKED = "BLOCKED"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class EvidenceMode(str, Enum):
    """Evidence validity classifications."""
    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    INFRASTRUCTURE_ONLY = "INFRASTRUCTURE_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


class NetworkRequirement(str, Enum):
    """Network dependency classifications."""
    NETWORK_REQUIRED = "NETWORK_REQUIRED"
    NETWORK_OPTIONAL = "NETWORK_OPTIONAL"
    NETWORK_NOT_REQUIRED = "NETWORK_NOT_REQUIRED"


class ExecutionMode(str, Enum):
    """Execution modality classifications."""
    DRY_RUN = "DRY_RUN"
    OFFLINE_VALIDATION = "OFFLINE_VALIDATION"
    TRAINING = "TRAINING"
    INFERENCE = "INFERENCE"
    ABLATION = "ABLATION"


class Stage42Decision(str, Enum):
    """Authoritative Stage 42 outcome decisions."""
    FRAMEWORK_VERIFIED_EXTERNAL_UNVERIFIED = (
        "STAGE 42 COMPLETE, FREE COMPUTE FRAMEWORK VERIFIED, EXTERNAL RUNTIME STILL UNVERIFIED"
    )
    FRAMEWORK_VERIFIED = "STAGE 42 COMPLETE, FREE COMPUTE FRAMEWORK VERIFIED"
    BLOCKED = "STAGE 42 BLOCKED, EVIDENCE RECORDED"


@dataclass
class HardwareProfile:
    """Detailed host hardware and environment audit."""
    os_name: str
    os_release: str
    architecture: str
    python_version: str
    cpu_model: str
    cpu_count_physical: int
    cpu_count_logical: int
    total_ram_gb: float
    available_ram_gb: float
    free_disk_gb: float
    gpu_count: int
    gpu_model: Optional[str] = None
    per_gpu_vram_gb: Optional[float] = None
    cuda_available: bool = False
    cuda_version: Optional[str] = None
    driver_version: Optional[str] = None
    classification: str = CUDACapability.NO_CUDA_GPU.value
    is_integrated_gpu: bool = False
    environment_class: EnvironmentClass = EnvironmentClass.LOCAL_CPU

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["environment_class"] = self.environment_class.value
        return d


@dataclass
class SoftwareProfile:
    """Software dependencies and package audit."""
    python_version: str
    packages: Dict[str, Optional[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComputeFingerprint:
    """Sanitized, deterministic compute environment fingerprint."""
    fingerprint_sha256: str
    normalized_record: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint_sha256": self.fingerprint_sha256,
            "normalized_record": self.normalized_record,
        }


@dataclass
class CapabilityItem:
    """Individual capability specification."""
    name: str
    supported: bool
    verified_status: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CapabilityMatrix:
    """Machine-readable capability matrix distinguishing design from reality."""
    environment_class: str
    capabilities: Dict[str, CapabilityItem] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_class": self.environment_class,
            "capabilities": {k: v.to_dict() for k, v in self.capabilities.items()},
        }


@dataclass
class EnvironmentContract:
    """Experiment environment contract binding requirements to observations."""
    environment_id: str
    environment_class: str
    experiment_id: str
    required_capabilities: List[str]
    required_gpu_memory: str
    required_cuda: bool
    required_python: str
    required_packages: List[str]
    actual_capabilities: List[str]
    compatibility_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactTransferItem:
    """Individual artifact entry in a transfer manifest."""
    relative_path: str
    sha256: str
    size_bytes: int
    category: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactTransferManifest:
    """Manifest of artifacts transferred between environments."""
    manifest_id: str
    created_at: str
    source_environment: str
    target_environment: str
    items: List[ArtifactTransferItem] = field(default_factory=list)
    total_size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "created_at": self.created_at,
            "source_environment": self.source_environment,
            "target_environment": self.target_environment,
            "items": [item.to_dict() for item in self.items],
            "total_size_bytes": self.total_size_bytes,
        }


@dataclass
class ReturnArtifactManifest:
    """Manifest of execution outputs and metrics returned from external runs."""
    run_id: str
    environment_fingerprint_sha256: str
    metrics: Dict[str, Any]
    artifacts: List[Dict[str, str]]
    result_hash: str
    execution_mode: str
    environment_class: str
    evidence_mode: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PreflightCheckResult:
    """Result of experiment preflight verification."""
    status: PreflightStatus
    experiment_id: str
    environment_class: EnvironmentClass
    passed_checks: List[str] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)
    blocking_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fingerprint_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "experiment_id": self.experiment_id,
            "environment_class": self.environment_class.value,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "fingerprint_sha256": self.fingerprint_sha256,
        }


@dataclass
class BootstrapMetadata:
    """Audit record for external environment bootstrap runs."""
    script_version: str
    git_commit: str
    environment_fingerprint: str
    package_versions: Dict[str, Optional[str]]
    start_time: str
    end_time: Optional[str]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
