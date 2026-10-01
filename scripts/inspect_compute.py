#!/usr/bin/env python3
"""CLI Utility for Inspecting and Auditing the Compute Environment (Stage 42 Section 7).

Usage:
    python scripts/inspect_compute.py --report
    python scripts/inspect_compute.py --hardware
    python scripts/inspect_compute.py --software
    python scripts/inspect_compute.py --capabilities
    python scripts/inspect_compute.py --fingerprint
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

from local.compute.capabilities import get_capability_matrix
from local.compute.fingerprint import generate_compute_fingerprint
from local.compute.hardware import detect_hardware
from local.compute.reporting import generate_stage42_report, write_stage42_reports
from local.compute.software import audit_software


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 42: Compute Environment Inspector",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--report",
        action="store_true",
        help="Generates and prints authoritative Stage 42 compute report.",
    )
    group.add_argument(
        "--hardware",
        action="store_true",
        help="Outputs hardware profile (CPU, RAM, GPU, CUDA) as JSON.",
    )
    group.add_argument(
        "--software",
        action="store_true",
        help="Outputs installed software dependency versions as JSON.",
    )
    group.add_argument(
        "--capabilities",
        action="store_true",
        help="Outputs capability matrix for the detected environment as JSON.",
    )
    group.add_argument(
        "--fingerprint",
        action="store_true",
        help="Outputs deterministic sanitized compute fingerprint as JSON.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="With --report, writes report files to experiments/compute/ and repo root.",
    )

    parsed = parser.parse_args(args)

    hw = detect_hardware(REPO_ROOT)
    sw = audit_software()

    if parsed.hardware:
        print(json.dumps(hw.to_dict(), indent=2))
        return 0

    if parsed.software:
        print(json.dumps(sw.to_dict(), indent=2))
        return 0

    if parsed.capabilities:
        caps = get_capability_matrix(hw.environment_class)
        print(json.dumps(caps.to_dict(), indent=2))
        return 0

    if parsed.fingerprint:
        fp = generate_compute_fingerprint(hw, sw)
        print(json.dumps(fp.to_dict(), indent=2))
        return 0

    if parsed.report:
        report_text = generate_stage42_report(REPO_ROOT, hw, sw)
        print(report_text)
        if parsed.write:
            write_stage42_reports(REPO_ROOT)
            print("[SUCCESS] Stage 42 reports written to experiments/compute/ and repo root.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
