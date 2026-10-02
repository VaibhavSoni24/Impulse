#!/usr/bin/env python3
"""CLI utility to promote a candidate through the Stage 44 promotion gate.

FAIL-CLOSED GUARANTEE:
- Candidate MUST satisfy all 5 promotion dimensions.
- If gate decision is not PROMOTE, the promotion action is strictly aborted.
- NO --force flag or bypass option exists or is permitted.

Usage:
  python scripts/promote_candidate.py E1
  python scripts/promote_candidate.py M1 --baseline M0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local.promotion.errors import ForbiddenBypassError, PromotionGateFailureError
from local.promotion.gate import PromotionGate


def main() -> None:
    # Explicitly check raw sys.argv for forbidden bypass attempts
    for arg in sys.argv:
        if arg in ("--force", "-f", "--bypass", "--skip-gate", "--override"):
            raise ForbiddenBypassError(
                f"Forbidden bypass option '{arg}' is strictly prohibited. The promotion gate is fail-closed."
            )

    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 44 — Fail-closed candidate promotion utility."
    )
    parser.add_argument("candidate_id", help="Candidate ID to promote (e.g. E1, M1)")
    parser.add_argument("--baseline", default=None, help="Optional explicit baseline candidate ID")
    parser.add_argument("--actor", default="IMPULSE-CLI", help="Actor name recording the promotion")
    parser.add_argument("--notes", default="", help="Optional audit notes")

    args = parser.parse_args()

    gate = PromotionGate(repo_root=REPO_ROOT)

    print(f"=== Initiating Fail-Closed Promotion: {args.candidate_id} ===")
    try:
        record = gate.promote_candidate(
            candidate_id=args.candidate_id,
            baseline_id=args.baseline,
            actor=args.actor,
            notes=args.notes,
            save_record=True,
        )
        print(f"[SUCCESS] Candidate '{args.candidate_id}' promoted successfully!")
        print(f"Decision Record: experiments/candidates/promotions/{args.candidate_id}.json")
        print(f"Promotion Report: experiments/candidates/promotions/{args.candidate_id}.md")
        sys.exit(0)

    except PromotionGateFailureError as exc:
        print(f"[FAILED] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] Promotion execution failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
