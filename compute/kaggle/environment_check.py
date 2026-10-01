#!/usr/bin/env python3
"""Kaggle Environment Diagnostic and Fingerprint Script."""

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
