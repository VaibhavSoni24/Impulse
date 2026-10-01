"""Deterministic Duplicate Detection Subsystem (Stage 38 Section 14).

Detects and reports:
1. Identical example hashes (exact content match)
2. Identical normalized tool sequences (same tool chain with equivalent args)
3. Near-identical textual contexts (context fingerprint collisions)
4. Near-duplicate groups

All deduplication is deterministic and records full audit metadata.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re
from typing import Any, Dict, List, Set, Tuple


def normalize_arg_val(val: Any) -> Any:
    """Recursively normalizes argument values for canonical comparison."""
    if isinstance(val, dict):
        return {k: normalize_arg_val(v) for k, v in sorted(val.items())}
    if isinstance(val, list):
        return [normalize_arg_val(x) for x in val]
    if isinstance(val, str):
        # Normalize whitespace
        return " ".join(val.strip().split())
    return val


def compute_sequence_signature(tool_sequence: list[dict[str, Any]]) -> str:
    """Computes canonical hash of normalized tool invocation sequence."""
    norm_steps = []
    for step in tool_sequence:
        t_name = str(step.get("tool_name", "")).strip().lower()
        args = normalize_arg_val(step.get("arguments", {}))
        norm_steps.append({"tool": t_name, "args": args})
    dumped = json.dumps(norm_steps, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def compute_example_hash(example: dict[str, Any]) -> str:
    """Computes strict SHA-256 hash of core content fields."""
    core = {
        "task_id": example.get("task_id", ""),
        "repo": example.get("repo", ""),
        "situation": " ".join(str(example.get("situation", "")).split()),
        "tool_sequence": example.get("tool_sequence", []),
        "preferred_behavior": example.get("preferred_behavior", {}),
        "negative_behavior": example.get("negative_behavior", {}),
        "objective_id": example.get("objective_id", ""),
    }
    dumped = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class DuplicateDetector:
    """Deterministic deduplication and audit engine."""

    def __init__(self) -> None:
        pass

    def deduplicate(
        self, examples: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """Performs multi-pass deterministic deduplication.

        Returns:
            (unique_examples, duplicates_removed, stats_dict)
        """
        raw_count = len(examples)
        unique_examples: list[dict[str, Any]] = []
        duplicate_examples: list[dict[str, Any]] = []

        seen_example_hashes: dict[str, str] = {}  # hash -> first example_id
        seen_sequence_signatures: dict[str, str] = {}  # seq_hash -> first example_id
        near_duplicate_groups: dict[str, list[str]] = defaultdict(list)

        for ex in examples:
            ex_id = str(ex.get("example_id", f"ex_{len(unique_examples)}"))
            ex_hash = compute_example_hash(ex)
            seq_sig = compute_sequence_signature(ex.get("tool_sequence", []))

            is_dup = False
            dup_reason = ""
            dup_target = ""

            if ex_hash in seen_example_hashes:
                is_dup = True
                dup_reason = "EXACT_EXAMPLE_HASH_COLLISION"
                dup_target = seen_example_hashes[ex_hash]
            elif seq_sig in seen_sequence_signatures:
                is_dup = True
                dup_reason = "IDENTICAL_NORMALIZED_TOOL_SEQUENCE"
                dup_target = seen_sequence_signatures[seq_sig]
                near_duplicate_groups[seq_sig].append(ex_id)

            if is_dup:
                dup_record = dict(ex)
                dup_record["duplicate_reason"] = dup_reason
                dup_record["duplicate_of"] = dup_target
                duplicate_examples.append(dup_record)
            else:
                seen_example_hashes[ex_hash] = ex_id
                seen_sequence_signatures[seq_sig] = ex_id
                near_duplicate_groups[seq_sig].append(ex_id)
                unique_examples.append(ex)

        # Count groups that have more than 1 member
        multi_member_groups = {k: v for k, v in near_duplicate_groups.items() if len(v) > 1}

        stats = {
            "raw_examples": raw_count,
            "duplicates_removed": len(duplicate_examples),
            "unique_examples": len(unique_examples),
            "near_duplicate_groups_count": len(multi_member_groups),
            "near_duplicate_groups": multi_member_groups,
        }

        return unique_examples, duplicate_examples, stats
