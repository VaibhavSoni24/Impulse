#!/usr/bin/env python3
"""Convenience CLI script for the IMPULSE Failure Dashboard (Stage 30).

Usage:
    python scripts/generate_dashboard.py --candidate E0 --split dev
    python scripts/generate_dashboard.py --candidate M0 --split validation
    python scripts/generate_dashboard.py --verify --output-dir experiments/dashboard/E0/dev
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.dashboard.cli import main

if __name__ == "__main__":
    sys.exit(main())
