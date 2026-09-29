"""Manifest management, validation, and source change detection (Stage 29 Phase 12, 21).

Provides:
- Serialization and deserialization of SplitManifest
- Cryptographic integrity validation of manifest and split files
- Automated source change detection to prevent stale split reuse
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.splits.hashing import (
    compute_canonical_task_set_hash,
    compute_file_sha256,
    compute_manifest_sha256,
)
from benchmark.splits.models import (
    ExclusionRecord,
    SourceDatasetMetadata,
    SplitInfo,
    SplitManifest,
)


def load_manifest(manifest_path: Path | str) -> SplitManifest:
    """Loads and deserializes a SplitManifest from a JSON file."""
    p = Path(manifest_path)
    if not p.is_file():
        raise FileNotFoundError(f"Manifest file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    src_data = data["source"]
    source = SourceDatasetMetadata(
        source_path=src_data["source_path"],
        source_sha256=src_data["source_sha256"],
        record_count=src_data["record_count"],
        format=src_data.get("format", "jsonl"),
        unique_repos=src_data.get("unique_repos", []),
        unique_commits=src_data.get("unique_commits", 0),
    )

    splits: dict[str, SplitInfo] = {}
    for s_name, s_data in data["splits"].items():
        splits[s_name] = SplitInfo(
            name=s_data["name"],
            task_count=s_data["task_count"],
            task_ids=s_data["task_ids"],
            repo_counts=s_data.get("repo_counts", {}),
            task_set_sha256=s_data["task_set_sha256"],
            file_sha256=s_data["file_sha256"],
            file_relative_path=s_data["file_relative_path"],
        )

    exclusions = [
        ExclusionRecord(
            instance_id=e["instance_id"],
            reason=e["reason"],
            policy_rule=e["policy_rule"],
            source_fingerprint=e.get("source_fingerprint", ""),
        )
        for e in data.get("exclusions", [])
    ]

    return SplitManifest(
        manifest_version=data["manifest_version"],
        policy_name=data["policy_name"],
        policy_version=data["policy_version"],
        generator_version=data["generator_version"],
        git_commit=data["git_commit"],
        created_at=data["created_at"],
        source=source,
        splits=splits,
        exclusions=exclusions,
        policy_config=data.get("policy_config", {}),
        manifest_sha256=data.get("manifest_sha256", ""),
    )


def save_manifest(manifest: SplitManifest, output_path: Path | str) -> None:
    """Saves a SplitManifest to filesystem with its canonical manifest_sha256."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    manifest_dict = manifest.to_dict(include_hash=False)
    calculated_hash = compute_manifest_sha256(manifest_dict)
    manifest.manifest_sha256 = calculated_hash

    full_dict = manifest.to_dict(include_hash=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(full_dict, f, indent=2, sort_keys=True)
        f.write("\n")


def verify_manifest_integrity(
    manifest_path: Path | str,
    base_dir: Path | str,
) -> tuple[bool, list[str]]:
    """Verifies that all split files in base_dir match the manifest hashes."""
    base_p = Path(base_dir)
    manifest = load_manifest(manifest_path)
    errors: list[str] = []

    # 1. Verify manifest self-hash
    computed_manifest_hash = compute_manifest_sha256(manifest.to_dict(include_hash=False))
    if manifest.manifest_sha256 != computed_manifest_hash:
        errors.append(
            f"Manifest self-hash tampered: expected {manifest.manifest_sha256[:12]}, got {computed_manifest_hash[:12]}"
        )

    # 2. Verify each split file
    for s_name, s_info in manifest.splits.items():
        file_p = base_p / s_info.file_relative_path
        if not file_p.is_file():
            errors.append(f"Split file missing: {file_p}")
            continue

        actual_file_hash = compute_file_sha256(file_p)
        if actual_file_hash != s_info.file_sha256:
            errors.append(
                f"Split file {s_name} ({s_info.file_relative_path}) file_sha256 mismatch: "
                f"expected {s_info.file_sha256[:12]}, got {actual_file_hash[:12]}"
            )

        # Verify task records count and task set hash
        with open(file_p, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]

        if len(records) != s_info.task_count:
            errors.append(
                f"Split {s_name} count mismatch: expected {s_info.task_count}, actual {len(records)}"
            )

        actual_set_hash = compute_canonical_task_set_hash(records)
        if actual_set_hash != s_info.task_set_sha256:
            errors.append(
                f"Split {s_name} task_set_sha256 mismatch: expected {s_info.task_set_sha256[:12]}, got {actual_set_hash[:12]}"
            )

    return len(errors) == 0, errors


def detect_source_change(
    manifest: SplitManifest,
    current_source_path: Path | str,
) -> tuple[bool, str]:
    """Detects if the source dataset has changed compared to the manifest."""
    src_p = Path(current_source_path)
    if not src_p.is_file():
        return True, f"Current source dataset file not found: {src_p}"

    current_sha256 = compute_file_sha256(src_p)
    if current_sha256 != manifest.source.source_sha256:
        return (
            True,
            f"Source dataset modified: manifest hash {manifest.source.source_sha256[:12]} != current hash {current_sha256[:12]}",
        )

    return False, "Source dataset unchanged"
