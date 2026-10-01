#!/usr/bin/env python3
"""CLI script runner for IMPULSE Stage 38: Construct LoRA Training Data."""

import sys
from pathlib import Path

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from local.lora_data.cli import run_cli

if __name__ == "__main__":
    sys.exit(run_cli())
