#!/usr/bin/env python3
"""Convenience CLI script for the IMPULSE LoRA Feasibility / Readiness Study (Stage 37 Section 20).

Usage:
    python scripts/run_lora_feasibility.py --verify
    python scripts/run_lora_feasibility.py --report
    python scripts/run_lora_feasibility.py --hardware
    python scripts/run_lora_feasibility.py --objectives
    python scripts/run_lora_feasibility.py --contract
    python scripts/run_lora_feasibility.py --setup
    python scripts/run_lora_feasibility.py --json
    python scripts/run_lora_feasibility.py --dry-run
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.lora_opt.cli import main

if __name__ == "__main__":
    sys.exit(main())
