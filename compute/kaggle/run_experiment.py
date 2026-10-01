#!/usr/bin/env python3
"""Provider-Neutral Kaggle Experiment Execution Entrypoint."""

import argparse
import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from local.compute.hardware import detect_hardware
from local.compute.software import audit_software
from local.compute.fingerprint import generate_compute_fingerprint
from local.compute.compatibility import evaluate_experiment_compatibility

def main():
    parser = argparse.ArgumentParser(description="IMPULSE Kaggle Experiment Runner")
    parser.add_argument("--experiment", type=str, required=True, help="Experiment identifier (e.g. L1, M0)")
    parser.add_argument("--dry-run", action="store_true", help="Perform preflight without executing")
    args = parser.parse_args()

    hw = detect_hardware(repo_root)
    sw = audit_software()
    fp = generate_compute_fingerprint(hw, sw)
    contract = evaluate_experiment_compatibility(args.experiment, hw, sw)

    print(f"Experiment ID:        {args.experiment}")
    print(f"Environment Class:    {hw.environment_class.value}")
    print(f"Compatibility Status: {contract.compatibility_status}")
    print(f"Fingerprint:          {fp.fingerprint_sha256}")

    if contract.compatibility_status != "READY":
        print(f"EXECUTION BLOCKED: Environment compatibility status is {contract.compatibility_status}")
        sys.exit(1)

    if args.dry_run:
        print("Dry run completed successfully.")
        sys.exit(0)

    print("Ready for experiment execution under invariant configuration.")

if __name__ == "__main__":
    main()
