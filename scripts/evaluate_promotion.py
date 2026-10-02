#!/usr/bin/env python3
"""CLI utility to evaluate candidates through the Stage 44 promotion gate.

Usage:
  python scripts/evaluate_promotion.py E0
  python scripts/evaluate_promotion.py E1
  python scripts/evaluate_promotion.py --candidate M0
  python scripts/evaluate_promotion.py --all
  python scripts/evaluate_promotion.py --all --save
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local.promotion.gate import PromotionGate
from local.versioning.registry import CandidateRegistry


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 44 — Evaluate candidate promotion gate."
    )
    parser.add_argument("candidate", nargs="?", default=None, help="Candidate ID to evaluate (e.g. E0, E1, M0)")
    parser.add_argument("--candidate", dest="candidate_opt", default=None, help="Candidate ID option")
    parser.add_argument("--baseline", default=None, help="Optional explicit baseline candidate ID")
    parser.add_argument("--all", action="store_true", help="Evaluate all registered candidates in registry")
    parser.add_argument("--save", action="store_true", help="Persist evaluation records to experiments/candidates/promotions/")

    args = parser.parse_args()
    candidate_id = args.candidate_opt or args.candidate

    if not args.all and not candidate_id:
        parser.error("Must specify a candidate ID or --all.")

    gate = PromotionGate(repo_root=REPO_ROOT)
    registry = CandidateRegistry(repo_root=REPO_ROOT)

    candidates_to_eval = []
    if args.all:
        candidates_to_eval = registry.list_candidate_ids()
    else:
        candidates_to_eval = [candidate_id]

    print("==========================================================================================")
    print(f"IMPULSE CANDIDATE PROMOTION GATE (Version {gate.evaluate.__globals__.get('PROMOTION_GATE_VERSION', '1.0.0')})")
    print("==========================================================================================")
    print(f"{'Candidate':<10} {'Baseline':<10} {'Validation':<12} {'Held-Out':<10} {'Runtime':<10} {'Config':<10} {'Repro':<10} {'Decision':<10}")
    print("-" * 90)

    evaluations = []
    for cid in candidates_to_eval:
        try:
            record = gate.evaluate(cid, baseline_id=args.baseline)
            evaluations.append(record)

            val_st = record.validation_result.get("dimension_status", "UNKNOWN")
            held_st = record.held_out_result.get("dimension_status", "UNKNOWN")
            rt_st = record.runtime_result.get("dimension_status", "UNKNOWN")
            cfg_st = record.configuration_result.get("dimension_status", "UNKNOWN")
            rep_st = record.reproducibility_result.get("dimension_status", "UNKNOWN")
            base = record.baseline_candidate_id or "ROOT"

            print(f"{cid:<10} {base:<10} {val_st:<12} {held_st:<10} {rt_st:<10} {cfg_st:<10} {rep_st:<10} {record.decision:<10}")

            if args.save:
                cand = registry.get_candidate(cid)
                base_cand = registry.get_candidate(record.baseline_candidate_id) if record.baseline_candidate_id else None
                if cand:
                    gate.save_promotion_record(record, cand, base_cand)

        except Exception as exc:
            print(f"{cid:<10} ERROR: {exc}")

    print("=" * 90)

    # Print summary counts
    promoted = sum(1 for e in evaluations if e.decision == "PROMOTE")
    rejected = sum(1 for e in evaluations if e.decision == "REJECT")
    blocked = sum(1 for e in evaluations if e.decision == "BLOCKED")

    print(f"Summary: Evaluated: {len(evaluations)} | PROMOTE: {promoted} | REJECT: {rejected} | BLOCKED: {blocked}")
    if args.save:
        print(f"Decision records and markdown reports saved to: experiments/candidates/promotions/")


if __name__ == "__main__":
    main()
