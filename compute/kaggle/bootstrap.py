#!/usr/bin/env python3
"""Python Bootstrap Script for Kaggle Notebooks."""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add repo root to path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from local.compute.hardware import detect_hardware
from local.compute.software import audit_software
from local.compute.fingerprint import generate_compute_fingerprint
from local.compute.bootstrap import record_bootstrap_execution

def main():
    start_time = datetime.now(timezone.utc).isoformat()
    hw = detect_hardware(repo_root)
    sw = audit_software()
    fp = generate_compute_fingerprint(hw, sw)

    meta = record_bootstrap_execution(
        script_version="1.0.0",
        git_commit="HEAD",
        environment_fingerprint=fp.fingerprint_sha256,
        package_versions=sw.packages,
        start_time=start_time,
        status="INITIALIZED",
    )

    print(f"Bootstrap initialized with fingerprint: {meta.environment_fingerprint}")
    print(f"Environment class: {hw.environment_class.value}")

if __name__ == "__main__":
    main()
