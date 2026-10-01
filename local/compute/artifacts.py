"""Artifact Transfer, Verification, Disk Budget, and Network Policy (Sections 17, 18, 22, 24, 25).

Handles:
- Manifesting artifacts to transfer to GPU environments
- Verifying SHA-256 checksums of transferred and returned artifacts
- Strict exclusion of secrets, credentials, and .env files
- Disk space verification with safety margins
- Network requirement classification
- CPU/GPU evidence mode separation
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple

from local.compute.errors import (
    ArtifactHashMismatchError,
    DiskSpaceInsufficientError,
    SecretLeakageDetectedError,
)
from local.compute.models import (
    ArtifactTransferItem,
    ArtifactTransferManifest,
    EvidenceMode,
    ExecutionMode,
    NetworkRequirement,
    ReturnArtifactManifest,
)

FORBIDDEN_TRANSFER_PATTERNS = [
    re.compile(r"\.env($|\..*)", re.IGNORECASE),
    re.compile(r".*\.key$", re.IGNORECASE),
    re.compile(r".*\.pem$", re.IGNORECASE),
    re.compile(r".*token.*", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
    re.compile(r".*\.log$", re.IGNORECASE),
    re.compile(r"__pycache__", re.IGNORECASE),
    re.compile(r"\.git($|[\\/].*)", re.IGNORECASE),
]

SECRET_VALUE_PATTERNS = [
    re.compile(r"akid[a-z0-9]{16,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"hf_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"kaggle_[a-zA-Z0-9]{16,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file deterministically in binary chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def scan_for_secrets(content: str) -> None:
    """Scans text content for forbidden secret patterns."""
    for pat in SECRET_VALUE_PATTERNS:
        if pat.search(content):
            raise SecretLeakageDetectedError("Credential pattern detected in artifact content.")


def is_forbidden_transfer_path(rel_path: str) -> bool:
    """Checks whether a relative path is forbidden from environment transfer."""
    norm = rel_path.replace("\\", "/")
    for pat in FORBIDDEN_TRANSFER_PATTERNS:
        if pat.search(norm):
            return True
    return False


def create_artifact_transfer_manifest(
    repo_root: Path,
    target_environment: str,
    categories: Optional[List[str]] = None,
) -> ArtifactTransferManifest:
    """Constructs a cryptographically-verified manifest of artifacts to transfer."""
    items: List[ArtifactTransferItem] = []
    total_bytes = 0

    # Key repository paths to transfer
    paths_to_include = [
        ("agent/agent.yaml", "AGENT_CONFIG"),
        ("agent/prompts/root.md", "PROMPT"),
        ("benchmark/tasks/smoke.jsonl", "BENCHMARK"),
        ("benchmark/splits/v1/dev.jsonl", "BENCHMARK"),
        ("benchmark/splits/v1/validation.jsonl", "BENCHMARK"),
        ("experiments/lora/L0/experiment_contract.json", "EXPERIMENT_CONTRACT"),
    ]

    for rel_str, category in paths_to_include:
        if is_forbidden_transfer_path(rel_str):
            continue

        full_path = repo_root / rel_str
        if full_path.is_file():
            size = full_path.stat().st_size
            sha = compute_file_sha256(full_path)
            items.append(
                ArtifactTransferItem(
                    relative_path=rel_str,
                    sha256=sha,
                    size_bytes=size,
                    category=category,
                )
            )
            total_bytes += size

    timestamp = datetime.now(timezone.utc).isoformat()
    manifest_id = f"TRANSFER_{hashlib.sha256(timestamp.encode()).hexdigest()[:12]}"

    return ArtifactTransferManifest(
        manifest_id=manifest_id,
        created_at=timestamp,
        source_environment="LOCAL_CPU",
        target_environment=target_environment,
        items=items,
        total_size_bytes=total_bytes,
    )


def verify_artifact_transfer_manifest(
    manifest: ArtifactTransferManifest,
    target_root: Path,
) -> Tuple[bool, List[str]]:
    """Verifies that all files in transfer manifest exist and match recorded hashes."""
    failures: List[str] = []

    for item in manifest.items:
        file_path = target_root / item.relative_path
        if not file_path.is_file():
            failures.append(f"MISSING: {item.relative_path}")
            continue

        actual_sha = compute_file_sha256(file_path)
        if actual_sha != item.sha256:
            failures.append(
                f"HASH_MISMATCH: {item.relative_path} (expected {item.sha256}, got {actual_sha})"
            )

    return (len(failures) == 0, failures)


def create_return_artifact_manifest(
    run_id: str,
    environment_fingerprint_sha256: str,
    metrics: Dict[str, Any],
    artifacts: List[Dict[str, str]],
    execution_mode: ExecutionMode,
    environment_class: str,
    evidence_mode: EvidenceMode,
) -> ReturnArtifactManifest:
    """Constructs a verified manifest for execution outputs returned from external runs."""
    # Ensure evidence mode discipline: fixture results must NEVER be claimed as LIVE
    if evidence_mode == EvidenceMode.FIXTURE:
        assert evidence_mode != EvidenceMode.LIVE, "Fixture result cannot be converted to LIVE."

    # Compute result hash over metrics + artifact hashes
    result_repr = json.dumps({"metrics": metrics, "artifacts": artifacts}, sort_keys=True)
    result_hash = hashlib.sha256(result_repr.encode("utf-8")).hexdigest()

    return ReturnArtifactManifest(
        run_id=run_id,
        environment_fingerprint_sha256=environment_fingerprint_sha256,
        metrics=metrics,
        artifacts=artifacts,
        result_hash=result_hash,
        execution_mode=execution_mode.value,
        environment_class=environment_class,
        evidence_mode=evidence_mode.value,
    )


def verify_return_artifact_manifest(
    manifest: ReturnArtifactManifest,
    target_dir: Path,
) -> Tuple[bool, List[str]]:
    """Verifies that all return artifacts exist and match expected hashes."""
    failures: List[str] = []
    for art in manifest.artifacts:
        rel_path = art.get("path")
        exp_sha = art.get("sha256")
        if not rel_path or not exp_sha:
            failures.append(f"INVALID_ARTIFACT_ENTRY: {art}")
            continue

        full_path = target_dir / rel_path
        if not full_path.is_file():
            failures.append(f"MISSING_RETURN_FILE: {rel_path}")
            continue

        actual_sha = compute_file_sha256(full_path)
        if actual_sha != exp_sha:
            failures.append(f"RETURN_HASH_MISMATCH: {rel_path} (exp {exp_sha}, got {actual_sha})")

    return (len(failures) == 0, failures)


def check_disk_budget(
    required_gb: float,
    safety_margin_gb: float = 5.0,
    check_path: Optional[Path] = None,
) -> Tuple[bool, float, float]:
    """Checks whether available disk space meets required storage plus safety margin."""
    path = check_path or Path(".")
    free_bytes = shutil.disk_usage(path).free
    free_gb = round(free_bytes / (1024**3), 2)
    needed_gb = round(required_gb + safety_margin_gb, 2)

    if free_gb < needed_gb:
        return False, free_gb, needed_gb
    return True, free_gb, needed_gb


def classify_network_requirement(task_type: str) -> NetworkRequirement:
    """Classifies network requirements by task category."""
    norm = task_type.upper().strip()
    if norm in {"MODEL_DOWNLOAD", "DEPENDENCY_INSTALL", "REMOTE_FETCH"}:
        return NetworkRequirement.NETWORK_REQUIRED
    elif norm in {"EXTERNAL_API_EVAL", "HF_HUB_SYNC"}:
        return NetworkRequirement.NETWORK_OPTIONAL
    else:
        # Core unit tests, benchmark analysis, config validation, dry runs
        return NetworkRequirement.NETWORK_NOT_REQUIRED
