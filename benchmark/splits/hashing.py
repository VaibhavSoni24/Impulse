"""Deterministic hashing functions for benchmark dataset splits (Stage 29 Phase 13, 20).

Guarantees:
- Canonical task-set hashing independent of JSON key ordering or whitespace formatting.
- Streaming file SHA-256 hashing.
- Individual task fingerprinting.
- Canonical manifest integrity verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def compute_file_sha256(file_path: Path | str) -> str:
    """Computes streaming SHA-256 hex digest for a file."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found for SHA-256 calculation: {p}")

    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_task_fingerprint(task_dict: dict[str, Any]) -> str:
    """Computes a deterministic cryptographic fingerprint for a single task record.
    
    Extracts canonical identity attributes and normalizes line endings.
    """
    problem = str(task_dict.get("problem_statement", "")).replace("\r\n", "\n").strip()
    canonical_repr = {
        "instance_id": str(task_dict.get("instance_id", "")).strip(),
        "repo": str(task_dict.get("repo", "")).strip(),
        "base_commit": str(task_dict.get("base_commit", "")).strip(),
        "problem_statement": problem,
    }
    encoded = json.dumps(canonical_repr, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_canonical_task_set_hash(task_records: list[dict[str, Any]]) -> str:
    """Computes a deterministic SHA-256 hash representing a set of tasks.
    
    The hash is invariant to the initial input list order, JSON whitespace,
    and non-identity formatting differences. Tasks are canonically ordered
    by (repo, base_commit, instance_id).
    """
    if not task_records:
        return hashlib.sha256(b"[]").hexdigest()

    canonical_tasks = []
    for rec in task_records:
        problem = str(rec.get("problem_statement", "")).replace("\r\n", "\n").strip()
        canonical_tasks.append(
            {
                "instance_id": str(rec.get("instance_id", "")).strip(),
                "repo": str(rec.get("repo", "")).strip(),
                "base_commit": str(rec.get("base_commit", "")).strip(),
                "problem_statement": problem,
            }
        )

    # Sort deterministically
    canonical_tasks.sort(key=lambda t: (t["repo"], t["base_commit"], t["instance_id"]))

    encoded = json.dumps(canonical_tasks, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_manifest_sha256(manifest_dict: dict[str, Any]) -> str:
    """Computes the integrity hash of a split manifest.
    
    Omits 'manifest_sha256' from the hashed payload.
    """
    cleaned = dict(manifest_dict)
    cleaned.pop("manifest_sha256", None)

    encoded = json.dumps(cleaned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
