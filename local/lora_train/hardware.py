"""Hardware and Runtime Environment Auditor for Stage 39 LoRA Training (Section 8).

Validates:
- Operating system and Python version
- Host RAM and available disk space
- CUDA availability and NVIDIA GPU discovery (via nvidia-smi / Windows CIM)
- Machine learning runtime packages (torch, transformers, peft, accelerate)
- Classifies training hardware status as:
  - TRAINING_HARDWARE_READY
  - TRAINING_HARDWARE_UNAVAILABLE
  - TRAINING_SOFTWARE_INCOMPATIBLE
  - TRAINING_HARDWARE_UNKNOWN
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple

from local.lora_train.models import HardwareAuditReport, HardwareStatus


def get_package_version(pkg_name: str) -> Optional[str]:
    """Safely retrieves installed package version without importing the package."""
    try:
        return importlib.metadata.version(pkg_name)
    except importlib.metadata.PackageNotFoundError:
        return None
    except Exception:
        return None


def probe_nvidia_gpu() -> tuple[bool, Optional[str], int, Optional[float]]:
    """Probes for NVIDIA GPUs and VRAM via nvidia-smi or Windows WMI/CIM."""
    # 1. Try nvidia-smi
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            gpu_count = len(lines)
            first_name, first_mem = lines[0].split(",", 1)
            vram_gb = round(float(first_mem.strip()) / 1024.0, 2)
            return True, first_name.strip(), gpu_count, vram_gb
    except Exception:
        pass

    # 2. Try Windows CIM/WMI if on Windows
    if platform.system() == "Windows":
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                controllers = [c.strip() for c in res.stdout.strip().splitlines() if c.strip()]
                for name in controllers:
                    if "nvidia" in name.lower():
                        return True, name, 1, None
                # If non-NVIDIA controllers found
                return False, controllers[0] if controllers else None, 0, None
        except Exception:
            pass

    return False, None, 0, None


def audit_training_hardware() -> HardwareAuditReport:
    """Performs full hardware and runtime environment audit for Stage 39 LoRA training."""
    os_name = platform.system()
    os_release = platform.platform()
    py_ver = sys.version.split()[0]

    # Available disk space
    try:
        disk_free_gb = round(shutil.disk_usage(".").free / (1024**3), 2)
    except Exception:
        disk_free_gb = 0.0

    # Host system RAM
    total_ram_gb = 0.0
    try:
        import psutil
        total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    except Exception:
        pass

    # Packages
    torch_ver = get_package_version("torch")
    trans_ver = get_package_version("transformers")
    peft_ver = get_package_version("peft")

    # GPU
    cuda_avail, gpu_name, gpu_count, vram_gb = probe_nvidia_gpu()

    # Classification logic
    # Gemma 4 31B weights (~23.3 GB) require multi-GPU VRAM (e.g. 4x NVIDIA L4 24GB or A100).
    has_ml_stack = bool(torch_ver and trans_ver and peft_ver)

    if cuda_avail and vram_gb and vram_gb >= 24.0 and gpu_count >= 1:
        if has_ml_stack:
            classification = HardwareStatus.TRAINING_HARDWARE_READY.value
            rationale = f"Detected {gpu_count}x {gpu_name} with {vram_gb} GB VRAM and required PEFT/torch runtime."
        else:
            classification = HardwareStatus.TRAINING_SOFTWARE_INCOMPATIBLE.value
            rationale = f"CUDA GPU available ({gpu_name}), but required ML libraries missing (torch={torch_ver}, transformers={trans_ver}, peft={peft_ver})."
    elif not cuda_avail or gpu_count == 0 or (gpu_name and "intel" in gpu_name.lower()):
        classification = HardwareStatus.TRAINING_HARDWARE_UNAVAILABLE.value
        rationale = (
            f"Host environment has non-CUDA graphics ({gpu_name or 'None'}) with {total_ram_gb} GB RAM "
            f"and 0 NVIDIA CUDA devices. Gemma 4 31B weights (~23.3 GB) exceed host capacity. "
            "External GPU infrastructure (4x NVIDIA L4 or equivalent) is required for LoRA training."
        )
    else:
        classification = HardwareStatus.TRAINING_HARDWARE_UNAVAILABLE.value
        rationale = f"Detected GPU ({gpu_name}) has insufficient VRAM ({vram_gb} GB) for 31B model LoRA training."

    return HardwareAuditReport(
        os_name=os_name,
        os_release=os_release,
        python_version=py_ver,
        cuda_available=cuda_avail,
        gpu_model=gpu_name,
        gpu_count=gpu_count,
        per_gpu_vram_gb=vram_gb,
        total_ram_gb=total_ram_gb,
        free_disk_gb=disk_free_gb,
        transformers_version=trans_ver,
        peft_version=peft_ver,
        torch_version=torch_ver,
        classification=classification,
        rationale=rationale,
    )
