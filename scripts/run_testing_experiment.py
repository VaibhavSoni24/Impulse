#!/usr/bin/env python3
"""Convenience CLI script for the IMPULSE Testing Strategy Optimization Loop (Stage 34).

Usage:
    python scripts/run_testing_experiment.py --parent T0 --analyze
    python scripts/run_testing_experiment.py --candidate T1 --diff
    python scripts/run_testing_experiment.py --candidate T1 --report
    python scripts/run_testing_experiment.py --matrix
    python scripts/run_testing_experiment.py --verify experiments/testing/T0
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.testing_opt.cli import main

if __name__ == "__main__":
    sys.exit(main())
