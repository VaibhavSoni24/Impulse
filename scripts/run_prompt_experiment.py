#!/usr/bin/env python3
"""Convenience CLI script for the IMPULSE Prompt Optimization Loop (Stage 32).

Usage:
    python scripts/run_prompt_experiment.py --parent P0 --analyze
    python scripts/run_prompt_experiment.py --candidate P1 --diff
    python scripts/run_prompt_experiment.py --candidate P1 --report
    python scripts/run_prompt_experiment.py --verify experiments/prompts/P0
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.prompt_opt.cli import main

if __name__ == "__main__":
    sys.exit(main())
