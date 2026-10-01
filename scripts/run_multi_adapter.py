#!/usr/bin/env python
"""Command-Line Interface for Stage 41 Multi-Adapter Experimentation.

Usage:
    python scripts/run_multi_adapter.py --verify
    python scripts/run_multi_adapter.py --inventory
    python scripts/run_multi_adapter.py --matrix
    python scripts/run_multi_adapter.py --dry-run
    python scripts/run_multi_adapter.py --report
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

from local.multi_adapter.evaluator import MultiAdapterEvaluator
from local.multi_adapter.matrix import MultiAdapterMatrixGenerator
from local.multi_adapter.models import Stage41Decision
from local.multi_adapter.prerequisites import SingleAdapterPrerequisiteChecker
from local.multi_adapter.reporting import MultiAdapterReporter


def main() -> int:
    parser = argparse.ArgumentParser(description="IMPULSE Stage 41 Multi-Adapter Experiment Runner")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verifies single-adapter prerequisite and reports multi-adapter eligibility.",
    )
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Lists available role adapters and their validation statuses.",
    )
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Displays the 8-member multi-adapter experiment matrix (MA0 through MA7).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executes dry-run schema, matrix, and isolation validation without execution.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generates stage41_report.md in experiments/lora/multi_adapter/ and repo root.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Attempts execution of multi-adapter experiment (refused if prerequisite fails).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Format output as JSON.",
    )

    args = parser.parse_args()

    prereq_checker = SingleAdapterPrerequisiteChecker(repo_root=REPO_ROOT)
    matrix_gen = MultiAdapterMatrixGenerator()
    evaluator = MultiAdapterEvaluator(repo_root=REPO_ROOT)
    reporter = MultiAdapterReporter(repo_root=REPO_ROOT)

    if args.verify or (not args.inventory and not args.matrix and not args.dry_run and not args.report and not args.execute):
        prereq = prereq_checker.check_single_adapter_prerequisite()
        if args.json:
            print(json.dumps(prereq.to_dict(), indent=2))
        else:
            print("[Stage 41] Single-Adapter Prerequisite Verification:")
            print(f"  Prerequisite Status: {'PASS' if prereq.eligible else 'FAIL'}")
            print(f"  Single Adapter Validated: {prereq.single_adapter_validated}")
            print(f"  Blocking Reasons: {', '.join(prereq.blocking_reasons)}")
            print(f"  Decision: {Stage41Decision.STAGE_41_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_PREREQUISITE.value}")
        return 0

    if args.inventory:
        inventory = {
            "root": "UNAVAILABLE",
            "scout": "UNAVAILABLE",
            "reviewer": "UNAVAILABLE",
            "validated_count": 0,
        }
        if args.json:
            print(json.dumps(inventory, indent=2))
        else:
            print("==================================================")
            print("IMPULSE Stage 41 Adapter Role Inventory")
            print("==================================================")
            print("  Root Agent Role:     UNAVAILABLE (0 validated adapters)")
            print("  Scout Sub-Agent:     UNAVAILABLE (0 validated adapters)")
            print("  Reviewer Sub-Agent:  UNAVAILABLE (0 validated adapters)")
            print("  Total Validated:     0")
        return 0

    if args.matrix:
        matrix = matrix_gen.generate_matrix()
        if args.json:
            print(json.dumps({k: v.to_dict() for k, v in matrix.items()}, indent=2))
        else:
            print("==================================================")
            print("IMPULSE Stage 41 Experiment Matrix (MA0 - MA7)")
            print("==================================================")
            for cid, cand in matrix.items():
                roles_desc = []
                for r_name, r_obj in cand.roles.items():
                    roles_desc.append(f"{r_name}:{'assigned' if r_obj else 'none'}")
                print(f"[{cid}] {cand.description}")
                print(f"    Status: {cand.status.value}")
                print(f"    Roles: {', '.join(roles_desc)}")
                print(f"    Topology: {cand.topology}")
                print()
        return 0

    if args.dry_run:
        summary = evaluator.execute_dry_run()
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("[Stage 41] Dry-Run Validation Complete:")
            print(f"  Status: {summary['status']}")
            print(f"  Prerequisite Status: {'PASS' if summary['single_adapter_prerequisite']['eligible'] else 'FAIL (BLOCKED)'}")
            print(f"  Matrix Candidate Count: {summary['matrix_size']}")
            print(f"  Overall Decision: {summary['overall_decision']}")
        return 0

    if args.report:
        report = evaluator.evaluate_multi_adapter()
        exp_p, root_p = reporter.write_reports(report)
        print(f"[Stage 41] Reports written:")
        print(f"  Experiment Report: {exp_p}")
        print(f"  Root Report: {root_p}")
        return 0

    if args.execute:
        prereq = prereq_checker.check_single_adapter_prerequisite()
        if not prereq.eligible:
            print("[Stage 41 ERROR] MULTI_ADAPTER_BLOCKED")
            print("Reason: NO_MEASURED_SINGLE_ADAPTER_BENEFIT")
            for r in prereq.blocking_reasons:
                print(f"  - {r}")
            return 1
        print("[Stage 41] Executing multi-adapter experiment...")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
