#!/usr/bin/env python3
"""Convenience CLI script for the IMPULSE Retrieval Optimization Loop (Stage 33).

Usage:
    python scripts/run_retrieval_experiment.py --parent R0 --analyze
    python scripts/run_retrieval_experiment.py --candidate R1 --diff
    python scripts/run_retrieval_experiment.py --candidate R1 --report
    python scripts/run_retrieval_experiment.py --matrix
    python scripts/run_retrieval_experiment.py --verify experiments/retrieval/R0
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.retrieval_opt.cli import main

if __name__ == "__main__":
    sys.exit(main())
