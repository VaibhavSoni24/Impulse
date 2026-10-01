"""Deterministic and Sanitized Compute Environment Fingerprinting (Section 10).

Computes a stable SHA-256 fingerprint representing the normalized execution
environment while strictly enforcing:
- Zero secrets or credentials
- Zero private paths or usernames
- Machine-invariant normalization across equivalent hardware setups
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict

from local.compute.errors import SecretLeakageDetectedError
from local.compute.models import (
    ComputeFingerprint,
    HardwareProfile,
    SoftwareProfile,
)

# Secret patterns to detect and forbid in fingerprints
SUSPICIOUS_PATTERNS = [
    re.compile(r"akid[a-z0-9]{16,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"hf_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"kaggle_[a-zA-Z0-9]{16,}", re.IGNORECASE),
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]", re.IGNORECASE),
    re.compile(r"[a-zA-Z]:\\[Users|home|root]", re.IGNORECASE),
]


def sanitize_value(val: Any) -> Any:
    """Recursively checks and ensures no credentials or personal paths leak into the fingerprint."""
    if isinstance(val, str):
        for pat in SUSPICIOUS_PATTERNS:
            if pat.search(val):
                raise SecretLeakageDetectedError(
                    f"Credential or personal path pattern detected in fingerprint value: '{val[:20]}...'"
                )
        return val
    elif isinstance(val, dict):
        return {k: sanitize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_value(item) for item in val]
    return val


def generate_compute_fingerprint(
    hardware: HardwareProfile,
    software: SoftwareProfile,
) -> ComputeFingerprint:
    """Generates a deterministic, normalized SHA-256 environment fingerprint."""
    # Normalize GPU identity: if integrated or no GPU, normalize to standard indicator
    if not hardware.cuda_available or hardware.is_integrated_gpu:
        normalized_gpu_model = "NONE" if hardware.gpu_count == 0 else "INTEGRATED_NON_CUDA"
    else:
        normalized_gpu_model = hardware.gpu_model or "UNKNOWN_CUDA_GPU"

    # Sorted package versions dictionary
    sorted_packages = {
        pkg: software.packages.get(pkg)
        for pkg in sorted(software.packages.keys())
    }

    normalized_record: Dict[str, Any] = {
        "architecture": hardware.architecture,
        "cuda_available": hardware.cuda_available,
        "cuda_version": hardware.cuda_version or "NONE",
        "driver_version": hardware.driver_version or "NONE",
        "gpu_count": hardware.gpu_count if hardware.cuda_available else 0,
        "gpu_model": normalized_gpu_model,
        "os_name": hardware.os_name,
        "packages": sorted_packages,
        "python_version": hardware.python_version,
    }

    # Ensure no secrets leak
    sanitize_value(normalized_record)

    # Deterministic JSON serialization
    serialized_canonical = json.dumps(normalized_record, sort_keys=True, separators=(",", ":"))
    fingerprint_sha256 = hashlib.sha256(serialized_canonical.encode("utf-8")).hexdigest()

    return ComputeFingerprint(
        fingerprint_sha256=fingerprint_sha256,
        normalized_record=normalized_record,
    )
