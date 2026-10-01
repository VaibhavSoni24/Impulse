"""Dataset and Artifact Manifest Generator (Stage 38 Section 23).

Generates:
1. experiments/lora/L1-data/manifests/dataset_manifest.json
2. experiments/lora/L1-data/manifests/file_manifest.json

Ensures strict reproducibility, cryptographic checksums computed from real bytes,
and complete tracking of parent commits, source hashes, and filter results.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.lora_data.models import DatasetManifest, DatasetStatus


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file's raw bytes."""
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_file_manifest(base_dir: Path) -> dict[str, str]:
    """Generates relative path to SHA-256 map for all files within base_dir."""
    manifest: dict[str, str] = {}
    if not base_dir.exists():
        return manifest

    for p in sorted(base_dir.rglob("*")):
        if p.is_file() and not p.name.endswith(".tmp"):
            rel_path = p.relative_to(base_dir).as_posix()
            manifest[rel_path] = compute_file_sha256(p)

    return manifest


def write_manifests(
    dataset_manifest: DatasetManifest,
    output_dir: Path,
    l1_data_root: Path,
) -> tuple[Path, Path]:
    """Writes dataset_manifest.json and file_manifest.json to output_dir.

    Returns:
        (dataset_manifest_path, file_manifest_path)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_manifest_path = output_dir / "dataset_manifest.json"
    file_manifest_path = output_dir / "file_manifest.json"

    # Compute hash of curated dataset files if present
    curated_dir = l1_data_root / "curated"
    train_file = curated_dir / "train.jsonl"
    val_file = curated_dir / "validation.jsonl"

    h = hashlib.sha256()
    if train_file.exists():
        h.update(train_file.read_bytes())
    if val_file.exists():
        h.update(val_file.read_bytes())
    dataset_manifest.dataset_sha256 = h.hexdigest()

    # Write dataset manifest
    with open(dataset_manifest_path, "w", encoding="utf-8") as f:
        json.dump(dataset_manifest.to_dict(), f, indent=2, sort_keys=True)

    # Generate and write file manifest
    file_manifest = generate_file_manifest(l1_data_root)
    with open(file_manifest_path, "w", encoding="utf-8") as f:
        json.dump(file_manifest, f, indent=2, sort_keys=True)

    return dataset_manifest_path, file_manifest_path
