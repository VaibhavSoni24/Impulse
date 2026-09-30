#!/usr/bin/env python3
"""Convenience CLI script for the IMPULSE Recovery Optimization Loop (Stage 35 Section 44).

Usage:
    python scripts/run_recovery_experiment.py --candidate REC0 --analyze
    python scripts/run_recovery_experiment.py --candidate REC1 --diff
    python scripts/run_recovery_experiment.py --candidate REC1 --report
    python scripts/run_recovery_experiment.py --matrix
    python scripts/run_recovery_experiment.py --verify experiments/recovery/REC0
    python scripts/run_recovery_experiment.py --mine-failures
    python scripts/run_recovery_experiment.py --cluster
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.recovery_opt.cli import main

if __name__ == "__main__":
    sys.exit(main())
