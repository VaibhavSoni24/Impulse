#!/usr/bin/env python3
"""CLI utility for generating and verifying reproducible benchmark dataset splits (Stage 29).

Usage:
    # Generate canonical v1 splits:
    python scripts/generate_splits.py --source data/competition/tasks.jsonl --output-dir benchmark/splits/v1

    # Verify existing split integrity:
    python scripts/generate_splits.py --verify --output-dir benchmark/splits/v1

    # Display audit report:
    python scripts/generate_splits.py --audit --output-dir benchmark/splits/v1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.splits.generator import SplitGenerator
from benchmark.splits.held_out_lock import verify_held_out_lock
from benchmark.splits.manifests import load_manifest, verify_manifest_integrity
from benchmark.splits.models import SplitPolicyType


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="IMPULSE Benchmark Dataset Split Generator (Stage 29)"
    )
    parser.add_argument(
        "--source",
        "-s",
        type=Path,
        default=Path("data/competition/tasks.jsonl"),
        help="Path to source tasks.jsonl (default: 'data/competition/tasks.jsonl').",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("benchmark/splits/v1"),
        help="Target directory for generated splits (default: 'benchmark/splits/v1').",
    )
    parser.add_argument(
        "--policy",
        "-p",
        type=str,
        default=SplitPolicyType.REPO_DISJOINT.value,
        choices=[p.value for p in SplitPolicyType],
        help="Split allocation policy (default: 'repo_disjoint').",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force regeneration even if output directory already contains splits.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify cryptographic integrity of existing splits against manifest.",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Print the formatted audit report for existing splits.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )

    args = parser.parse_args(argv)

    # 1. Audit display action
    if args.audit:
        audit_md_p = args.output_dir / "audit_report.md"
        if not audit_md_p.is_file():
            print(f"Error: Audit report not found at {audit_md_p}", file=sys.stderr)
            return 1
        print(audit_md_p.read_text(encoding="utf-8"))
        return 0

    # 2. Verification action
    if args.verify:
        manifest_p = args.output_dir / "manifest.json"
        if not manifest_p.is_file():
            print(f"Error: Manifest not found at {manifest_p}", file=sys.stderr)
            return 1

        is_valid, errors = verify_manifest_integrity(manifest_p, args.output_dir)
        lock_p = args.output_dir / "held_out.lock"
        held_out_p = args.output_dir / "held_out.jsonl"
        manifest = load_manifest(manifest_p)

        lock_valid, lock_msg = verify_held_out_lock(
            lock_path=lock_p,
            held_out_file_path=held_out_p,
            current_manifest_sha256=manifest.manifest_sha256,
        )

        overall_valid = is_valid and lock_valid

        if args.json:
            print(
                json.dumps(
                    {
                        "valid": overall_valid,
                        "manifest_valid": is_valid,
                        "lock_valid": lock_valid,
                        "lock_message": lock_msg,
                        "errors": errors,
                    },
                    indent=2,
                )
            )
        else:
            print("=" * 60)
            print("IMPULSE BENCHMARK SPLIT VERIFICATION")
            print("=" * 60)
            print(f"Output Directory:    {args.output_dir}")
            print(f"Manifest Status:     {'VALID' if is_valid else 'INVALID'}")
            print(f"Held-Out Lock:       {'LOCKED & VERIFIED' if lock_valid else 'FAILED: ' + lock_msg}")
            if errors:
                print("Errors:")
                for err in errors:
                    print(f"  - {err}")
            print(f"Overall Result:      {'PASS' if overall_valid else 'FAIL'}")
            print("=" * 60)

        return 0 if overall_valid else 1

    # 3. Generation action
    policy_enum = SplitPolicyType(args.policy)
    generator = SplitGenerator(
        source_path=args.source,
        output_dir=args.output_dir,
        policy_type=policy_enum,
    )

    try:
        manifest = generator.generate(force=args.force)
    except Exception as e:
        print(f"Error during split generation: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(manifest.to_dict(), indent=2))
    else:
        print("=" * 60)
        print("IMPULSE BENCHMARK SPLIT GENERATION COMPLETE (STAGE 29)")
        print("=" * 60)
        print(f"Source Dataset:      {manifest.source.source_path}")
        print(f"Source SHA-256:      {manifest.source.source_sha256[:16]}...")
        print(f"Source Records:      {manifest.source.record_count}")
        print(f"Policy:              {manifest.policy_name} (v{manifest.policy_version})")
        print(f"Manifest SHA-256:    {manifest.manifest_sha256[:16]}...")
        print("-" * 60)
        for s_name, s_info in manifest.splits.items():
            print(f"  {s_name.upper():<12}: {s_info.task_count:>3} tasks | SHA: {s_info.file_sha256[:12]}...")
        print(f"  EXCLUSIONS  : {len(manifest.exclusions):>3} tasks")
        print("=" * 60)
        print(f"Splits and manifests written to: {args.output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
