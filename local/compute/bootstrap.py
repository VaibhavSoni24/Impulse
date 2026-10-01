"""External Environment Bootstrap Generator and Runner for Stage 42 (Sections 15, 26).

Generates provider-neutral bootstrap scripts and execution wrappers for
external environments (e.g. Kaggle Notebooks, external Linux GPU).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional

from local.compute.models import BootstrapMetadata


def record_bootstrap_execution(
    script_version: str,
    git_commit: str,
    environment_fingerprint: str,
    package_versions: Dict[str, Optional[str]],
    start_time: str,
    end_time: Optional[str] = None,
    status: str = "COMPLETED",
) -> BootstrapMetadata:
    """Creates a deterministic, secret-free record of external bootstrap execution."""
    return BootstrapMetadata(
        script_version=script_version,
        git_commit=git_commit,
        environment_fingerprint=environment_fingerprint,
        package_versions=package_versions,
        start_time=start_time,
        end_time=end_time or datetime.now(timezone.utc).isoformat(),
        status=status,
    )


def generate_kaggle_bootstrap_bundle(target_dir: Path) -> Dict[str, Path]:
    """Generates the Kaggle execution scripts in compute/kaggle/."""
    target_dir.mkdir(parents=True, exist_ok=True)
    generated: Dict[str, Path] = {}

    # 1. README.md
    readme_path = target_dir / "README.md"
    readme_path.write_text(
        """# IMPULSE Kaggle Free GPU Execution Environment

This directory provides provider-neutral bootstrap and execution scripts for running IMPULSE experiments on Kaggle notebook sessions (T4x2 or P100).

## Governance & Safety Rules
1. **Zero Credentials:** Never commit or hardcode personal Kaggle API tokens (`kaggle.json`).
2. **Experiment Invariance:** The experiment configuration and prompts remain 100% invariant across environments.
3. **Evidence Separation:** Live external results must record their compute fingerprint and environment class (`KAGGLE_FREE_GPU`).
4. **Reproducibility:** All transferred artifacts are SHA-256 verified prior to execution.

## Execution Steps in Kaggle Notebook
1. Enable GPU accelerator (GPU T4x2 or P100) in Kaggle Notebook Settings.
2. Clone or unpack the verified IMPULSE repository snapshot.
3. Run the environment check:
   ```bash
   python compute/kaggle/environment_check.py
   ```
4. Execute the targeted experiment via preflight-verified runner:
   ```bash
   python compute/kaggle/run_experiment.py --experiment L1
   ```
""",
        encoding="utf-8",
    )
    generated["README.md"] = readme_path

    # 2. bootstrap.sh
    sh_path = target_dir / "bootstrap.sh"
    sh_path.write_text(
        """#!/usr/bin/env bash
# IMPULSE Kaggle Bootstrap Script (Section 15, 26)
set -euo pipefail

echo "=================================================="
echo "IMPULSE Kaggle Compute Environment Bootstrap"
echo "=================================================="

# Verify Python version
python3 --version

# Probe GPU via nvidia-smi
if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU Detected:"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
else
    echo "ERROR: No NVIDIA GPU detected. Enable GPU accelerator in Kaggle settings."
    exit 1
fi

# Run environment verification
python3 compute/kaggle/environment_check.py

echo "Bootstrap completed successfully."
""",
        encoding="utf-8",
    )
    generated["bootstrap.sh"] = sh_path

    # 3. environment_check.py
    env_check_path = target_dir / "environment_check.py"
    env_check_path.write_text(
        """#!/usr/bin/env python3
\"\"\"Kaggle Environment Diagnostic and Fingerprint Script.\"\"\"

import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from local.compute.hardware import detect_hardware
from local.compute.software import audit_software
from local.compute.fingerprint import generate_compute_fingerprint
from local.compute.capabilities import get_capability_matrix
from local.compute.models import EnvironmentClass

def main():
    print("=== IMPULSE Compute Environment Audit ===")
    hw = detect_hardware(repo_root)
    sw = audit_software()
    fp = generate_compute_fingerprint(hw, sw)
    caps = get_capability_matrix(hw.environment_class)

    print(f"OS:            {hw.os_name} ({hw.architecture})")
    print(f"Python:        {hw.python_version}")
    print(f"Environment:   {hw.environment_class.value}")
    print(f"CUDA:          {hw.cuda_available} (Version: {hw.cuda_version})")
    print(f"GPU Model:     {hw.gpu_model} (Count: {hw.gpu_count}, VRAM: {hw.per_gpu_vram_gb} GB)")
    print(f"Fingerprint:   {fp.fingerprint_sha256}")
    print("==========================================")

if __name__ == "__main__":
    main()
""",
        encoding="utf-8",
    )
    generated["environment_check.py"] = env_check_path

    # 4. run_experiment.py
    run_exp_path = target_dir / "run_experiment.py"
    run_exp_path.write_text(
        """#!/usr/bin/env python3
\"\"\"Provider-Neutral Kaggle Experiment Execution Entrypoint.\"\"\"

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
""",
        encoding="utf-8",
    )
    generated["run_experiment.py"] = run_exp_path

    # 5. bootstrap.py
    py_path = target_dir / "bootstrap.py"
    py_path.write_text(
        """#!/usr/bin/env python3
\"\"\"Python Bootstrap Script for Kaggle Notebooks.\"\"\"

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
""",
        encoding="utf-8",
    )
    generated["bootstrap.py"] = py_path

    return generated
