#!/usr/bin/env python
"""Command-Line Interface for Stage 40 LoRA Ablation.

Usage:
    python scripts/run_lora_ablation.py --verify
    python scripts/run_lora_ablation.py --conditions
    python scripts/run_lora_ablation.py --dry-run
    python scripts/run_lora_ablation.py --compare [--adapter-path <path>]
    python scripts/run_lora_ablation.py --report
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

from local.lora_ablation.adapter_gate import AdapterGateValidator
from local.lora_ablation.conditions import ConditionManager
from local.lora_ablation.evaluator import AblationEvaluator
from local.lora_ablation.models import (
    AdapterGateStatus,
    ConditionStatus,
    Stage40Decision,
)
from local.lora_ablation.reporting import AblationReporter


def main() -> int:
    parser = argparse.ArgumentParser(description="IMPULSE Stage 40 LoRA Ablation Runner")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verifies adapter availability and outputs condition readiness.",
    )
    parser.add_argument(
        "--conditions",
        action="store_true",
        help="Displays the four controlled ablation conditions (A, B, C, D).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executes dry-run invariance, schema, and manifest validation without execution.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Executes primary A/B comparison (enforcing Hard Adapter Gate).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generates stage40_report.md in experiments/lora/ and repo root.",
    )
    parser.add_argument(
        "--adapter-path",
        type=str,
        default=None,
        help="Optional path to candidate LoRA adapter directory.",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="dev",
        help="Benchmark split to evaluate (default: dev).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Format output as JSON.",
    )

    args = parser.parse_args()

    evaluator = AblationEvaluator(repo_root=REPO_ROOT)
    reporter = AblationReporter(repo_root=REPO_ROOT)
    cond_mgr = ConditionManager(repo_root=REPO_ROOT)

    if args.verify or (not args.conditions and not args.dry_run and not args.compare and not args.report):
        conditions = cond_mgr.build_all_conditions(args.adapter_path, benchmark_split=args.split)
        cond_b = conditions["B"]

        if args.json:
            print(json.dumps({k: v.to_dict() for k, v in conditions.items()}, indent=2))
        else:
            print("[Stage 40] Ablation Readiness Verification:")
            for cond_id, cond in conditions.items():
                print(f"  Condition {cond_id} ({cond.condition_type.value}): {cond.status.value}")
                if cond.status_reason:
                    print(f"    Reason: {cond.status_reason}")
            print(f"  Adapter Gate Status: {cond_b.status.value}")
            print(f"  Primary Status: {Stage40Decision.STAGE_40_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_MISSING_ADAPTER.value}")

        return 0

    if args.conditions:
        conditions = cond_mgr.build_all_conditions(args.adapter_path, benchmark_split=args.split)
        if args.json:
            print(json.dumps({k: v.to_dict() for k, v in conditions.items()}, indent=2))
        else:
            print("==================================================")
            print("IMPULSE Stage 40 Controlled Ablation Conditions")
            print("==================================================")
            for cid, cond in conditions.items():
                print(f"[{cid}] {cond.condition_label}")
                print(f"    Type: {cond.condition_type.value}")
                print(f"    Status: {cond.status.value}")
                print(f"    Candidate: {cond.candidate_id}")
                print(f"    Base Model: {cond.base_model}")
                print(f"    Adapter Enabled: {cond.adapter_enabled}")
                print(f"    Prompt Hash: {cond.prompt_hash[:16]}...")
                print(f"    Retrieval: {cond.retrieval_version}")
                print(f"    Topology: {cond.topology}")
                print()
        return 0

    if args.dry_run:
        summary = evaluator.execute_dry_run(args.adapter_path, benchmark_split=args.split)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("[Stage 40] Dry-Run Validation Complete:")
            print(f"  Status: {summary['status']}")
            print(f"  Condition A (Baseline): {summary['conditions']['A']['status']}")
            print(f"  Condition B (Adapter): {summary['conditions']['B']['status']}")
            print(f"  Condition C (Prompt Variant): {summary['conditions']['C']['status']}")
            print(f"  Condition D (Retrieval Variant): {summary['conditions']['D']['status']}")
            print(f"  Baseline Invariance: {'PASS' if summary['invariance_check']['baseline_a']['valid'] else 'FAIL'}")
            print(f"  A/B Comparison Invariance: {'PASS' if summary['invariance_check']['pair_a_b']['valid'] else 'FAIL'}")
            print(f"  Benchmark Manifest: {'READY' if summary['benchmark']['manifest_ready'] else 'NOT_FOUND'}")
            print(f"  Overall Decision: {summary['overall_decision']}")
        return 0

    if args.compare:
        report = evaluator.run_primary_ablation(args.adapter_path, benchmark_split=args.split)
        reporter.write_reports(report)

        if report.adapter_gate_status != AdapterGateStatus.READY:
            print(f"[Stage 40 BLOCKED] Hard Adapter Gate Failure: {report.decision_reason}")
            return 1

        print(f"[Stage 40] Primary A/B Ablation Complete: {report.overall_status.value}")
        return 0

    if args.report:
        report = evaluator.run_primary_ablation(args.adapter_path, benchmark_split=args.split)
        exp_p, root_p = reporter.write_reports(report)
        print(f"[Stage 40] Reports written:")
        print(f"  Experiment Report: {exp_p}")
        print(f"  Root Report: {root_p}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
