#!/usr/bin/env python3
"""CLI Utility for Validating Candidate Manifests (Stage 43 Section 25).

Usage:
    python scripts/validate_candidate.py <candidate_id>
    python scripts/validate_candidate.py --all
    python scripts/validate_candidate.py --all --json
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

from local.versioning.registry import CandidateRegistry
from local.versioning.validation import CandidateValidator


def validate_single_candidate(
    registry: CandidateRegistry,
    candidate_id: str,
    known_ids: set[str],
) -> tuple[bool, list[str], list[str]]:
    """Validates a single candidate manifest."""
    cand = registry.get_candidate(candidate_id)
    if not cand:
        return False, [f"Candidate '{candidate_id}' not found in registry."], []

    errors: list[str] = []
    warnings: list[str] = []

    try:
        warns = CandidateValidator.validate_manifest(cand, known_candidate_ids=known_ids)
        warnings.extend(warns)
    except Exception as e:
        errors.append(str(e))

    # Check manifest hash matches content
    cand_dict = cand.to_dict()
    recorded_hash = cand_dict.get("manifest_hash")
    from local.versioning.hashing import compute_canonical_dict_hash
    computed_hash = compute_canonical_dict_hash(cand_dict, exclude_keys=["manifest_hash"])
    if recorded_hash and recorded_hash != computed_hash:
        errors.append(
            f"Manifest hash mismatch: recorded {recorded_hash[:12]}, computed {computed_hash[:12]}"
        )

    return (len(errors) == 0, errors, warnings)


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IMPULSE Stage 43: Candidate Manifest Validator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("candidate_id", nargs="?", default=None, help="Candidate ID to validate (e.g. E0, M0, L1)")
    group.add_argument("--all", action="store_true", help="Validate all registered candidates")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    parsed = parser.parse_args(args)
    registry = CandidateRegistry(repo_root=REPO_ROOT)
    known_ids = set(registry.list_candidate_ids())

    targets = list(known_ids) if parsed.all else ([parsed.candidate_id] if parsed.candidate_id else [])
    if not targets:
        print("No candidates specified or found to validate.")
        return 1

    results: dict[str, dict] = {}
    all_ok = True

    for cid in sorted(targets):
        ok, errors, warnings = validate_single_candidate(registry, cid, known_ids)
        if not ok:
            all_ok = False
        results[cid] = {
            "status": "PASSED" if ok else "FAILED",
            "errors": errors,
            "warnings": warnings,
        }

    if parsed.json:
        print(json.dumps(results, indent=2))
    else:
        print("==================================================")
        print("IMPULSE CANDIDATE MANIFEST VALIDATION")
        print("==================================================")
        for cid, res in sorted(results.items()):
            icon = "[PASS]" if res["status"] == "PASSED" else "[FAIL]"
            print(f"{icon} Candidate: {cid:<8} Status: {res['status']}")
            for err in res["errors"]:
                print(f"       ERROR: {err}")
            for warn in res["warnings"]:
                print(f"       WARN:  {warn}")
        print("==================================================")
        print(f"Overall Result: {'ALL CANDIDATES PASSED' if all_ok else 'VALIDATION FAILURES DETECTED'}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
