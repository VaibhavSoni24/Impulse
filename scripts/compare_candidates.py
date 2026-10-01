#!/usr/bin/env python3
"""CLI Utility for Deterministic Candidate Comparison and Lineage Traversal (Stage 43 Section 27).

Usage:
    python scripts/compare_candidates.py <parent_id> <candidate_id> [--json]
    python scripts/compare_candidates.py --lineage <root_candidate_id>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local.versioning.comparison import CandidateComparator
from local.versioning.registry import CandidateRegistry


def print_lineage_tree(registry: CandidateRegistry, root_id: str, depth: int = 0) -> None:
    """Recursively prints candidate lineage tree."""
    cand = registry.get_candidate(root_id)
    if not cand:
        print(f"{'  ' * depth}- {root_id} (UNKNOWN)")
        return

    print(f"{'  ' * depth}* {cand.candidate_id} [{cand.status}] (dim: {cand.primary_dimension}, v{cand.candidate_version})")

    # Find children
    reg = registry.load_registry()
    children = [
        cid for cid, info in sorted(reg.get("candidates", {}).items())
        if info.get("parent") == root_id and cid != root_id
    ]
    for child in children:
        print_lineage_tree(registry, child, depth + 1)


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IMPULSE Stage 43: Candidate Comparator")
    parser.add_argument("candidates", nargs="*", help="Parent and candidate IDs to compare (e.g. E0 E1)")
    parser.add_argument("--lineage", type=str, default=None, help="Display lineage tree starting from specified root candidate")
    parser.add_argument("--json", action="store_true", help="Output comparison strictly in JSON format")

    parsed = parser.parse_args(args)
    registry = CandidateRegistry(repo_root=REPO_ROOT)

    if parsed.lineage:
        print(f"=== Candidate Lineage Tree from '{parsed.lineage}' ===")
        print_lineage_tree(registry, parsed.lineage)
        return 0

    if len(parsed.candidates) != 2:
        print("Usage: python scripts/compare_candidates.py <parent_id> <candidate_id> or --lineage <root_id>")
        return 1

    parent_id, candidate_id = parsed.candidates[0], parsed.candidates[1]
    parent_cand = registry.get_candidate(parent_id)
    candidate_cand = registry.get_candidate(candidate_id)

    if not parent_cand:
        print(f"ERROR: Parent candidate '{parent_id}' not found in registry.")
        return 1
    if not candidate_cand:
        print(f"ERROR: Candidate '{candidate_id}' not found in registry.")
        return 1

    result = CandidateComparator.compare(parent_cand, candidate_cand)

    if parsed.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print("==================================================")
        print(f"IMPULSE CANDIDATE COMPARISON: {parent_id} -> {candidate_id}")
        print("==================================================")
        print(f"Primary Changed Dimension: {candidate_cand.primary_dimension}")
        print(f"Multi-Dimension Experiment: {result.is_multi_dimension}")
        print(f"Changed Dimensions:         {result.changed_dimensions}")
        print(f"Unchanged Dimensions:       {result.unchanged_dimensions}")

        if result.hash_changes:
            print("\nHash Deltas:")
            for k, deltas in sorted(result.hash_changes.items()):
                print(f"  - {k}: parent={deltas.get('parent')[:8] if deltas.get('parent') else 'None'} -> cand={deltas.get('candidate')[:8] if deltas.get('candidate') else 'None'}")

        if result.configuration_changes:
            print("\nConfiguration Deltas:")
            for k, deltas in sorted(result.configuration_changes.items()):
                print(f"  - {k}: {deltas.get('parent')} -> {deltas.get('candidate')}")

        if result.benchmark_changes:
            print("\nBenchmark Deltas:")
            for k, deltas in sorted(result.benchmark_changes.items()):
                print(f"  - {k}: {deltas}")

        if result.adapter_changes:
            print("\nAdapter Deltas:")
            for k, deltas in sorted(result.adapter_changes.items()):
                print(f"  - {k}: {deltas}")

        if result.warnings:
            print("\nWarnings:")
            for w in result.warnings:
                print(f"  ! {w}")
        print("==================================================")

    return 0


if __name__ == "__main__":
    sys.exit(main())
