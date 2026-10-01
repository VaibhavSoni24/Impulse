#!/usr/bin/env python3
"""Convenience CLI script for the IMPULSE Skill Optimization Loop (Stage 36 Section 40).

Usage:
    python scripts/run_skill_experiment.py --inventory
    python scripts/run_skill_experiment.py --parent S0 --analyze
    python scripts/run_skill_experiment.py --candidate S1 --diff
    python scripts/run_skill_experiment.py --candidate S1 --report
    python scripts/run_skill_experiment.py --candidate S1 --verify
    python scripts/run_skill_experiment.py --matrix
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.skill_opt.cli import main

if __name__ == "__main__":
    sys.exit(main())
