#!/usr/bin/env bash
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
