#!/usr/bin/env python3
"""CLI Utility for Experiment Preflight Checks (Stage 42 Section 13).

Usage:
    python scripts/compute_preflight.py --experiment <id> [--json]
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

from local.compute.fingerprint import generate_compute_fingerprint
from local.compute.hardware import detect_hardware
from local.compute.models import PreflightStatus
from local.compute.preflight import ComputePreflightAuditor
from local.compute.software import audit_software


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 42: Experiment Preflight Verifier",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        required=True,
        help="Experiment identifier to audit (e.g. L1, MA1, M0, STAGE42_AUDIT)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result strictly formatted as JSON",
    )

    parsed = parser.parse_args(args)

    hw = detect_hardware(REPO_ROOT)
    sw = audit_software()
    fp = generate_compute_fingerprint(hw, sw)

    auditor = ComputePreflightAuditor(REPO_ROOT)
    res = auditor.run_preflight(parsed.experiment, hw=hw, sw=sw)
    res.fingerprint_sha256 = fp.fingerprint_sha256

    if parsed.json:
        print(json.dumps(res.to_dict(), indent=2))
    else:
        print("==================================================")
        print(f"IMPULSE COMPUTE PREFLIGHT AUDIT: {res.experiment_id}")
        print("==================================================")
        print(f"Status:            {res.status.value}")
        print(f"Environment Class: {res.environment_class.value}")
        print(f"Fingerprint:       {res.fingerprint_sha256}")
        print(f"Passed Checks:     {len(res.passed_checks)}")
        print(f"Failed Checks:     {len(res.failed_checks)}")
        if res.blocking_reasons:
            print("Blocking Reasons:")
            for reason in res.blocking_reasons:
                print(f"  - {reason}")
        if res.warnings:
            print("Warnings:")
            for w in res.warnings:
                print(f"  - {w}")
        print("==================================================")

    # Return code: 0 if READY, 1 if BLOCKED, 2 if INCOMPATIBLE, 3 if UNKNOWN
    if res.status == PreflightStatus.READY:
        return 0
    elif res.status == PreflightStatus.BLOCKED:
        return 1
    elif res.status == PreflightStatus.INCOMPATIBLE:
        return 2
    else:
        return 3


if __name__ == "__main__":
    sys.exit(main())
