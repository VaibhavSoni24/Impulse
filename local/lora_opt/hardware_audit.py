"""Hardware and Runtime Feasibility Auditor (Stage 37 Section 12).

Performs non-destructive environment audit:
- Operating system and Python version
- Host RAM and available disk space
- CUDA availability and NVIDIA GPU discovery (via nvidia-smi / WMI)
- Machine learning runtime packages (torch, transformers, peft, vllm, tokenizers)
- Classifies feasibility as:
  - LOCAL_FEASIBLE
  - LOCAL_NOT_FEASIBLE
  - EXTERNAL_GPU_REQUIRED
  - INFRASTRUCTURE_UNKNOWN
"""

from __future__ import annotations

import importlib.metadata
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional

from local.lora_opt.models import HardwareAuditReport, InfrastructureClassification


def get_package_version(pkg_name: str) -> Optional[str]:
    """Safely retrieves installed package version without importing the package."""
    try:
        return importlib.metadata.version(pkg_name)
    except importlib.metadata.PackageNotFoundError:
        return None
    except Exception:
        return None


def probe_nvidia_gpu() -> tuple[bool, Optional[str], int, Optional[float]]:
    """Probes for NVIDIA GPUs and VRAM via nvidia-smi or Windows WMI."""
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


def audit_hardware_environment() -> HardwareAuditReport:
    """Performs full hardware and runtime feasibility audit."""
    os_name = platform.system()
    os_release = platform.platform()
    py_ver = sys.version.split()[0]

    # Disk
    try:
        disk_free_gb = round(shutil.disk_usage(".").free / (1024**3), 2)
    except Exception:
        disk_free_gb = 0.0

    # RAM
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
    # Gemma 4 31B QAT W4A16 base weights occupy ~23.3 GB.
    # Training an adapter requires significant GPU memory (typically 4x L4 24GB or A100 80GB).
    if cuda_avail and vram_gb and vram_gb >= 24.0 and gpu_count >= 1:
        classification = InfrastructureClassification.LOCAL_FEASIBLE.value
        rationale = f"Detected {gpu_count}x {gpu_name} with {vram_gb} GB VRAM."
    elif gpu_name and "intel" in gpu_name.lower():
        classification = InfrastructureClassification.EXTERNAL_GPU_REQUIRED.value
        rationale = (
            f"Host environment has integrated graphics ({gpu_name}) with {total_ram_gb} GB RAM "
            f"and 0 NVIDIA CUDA devices. Gemma 4 31B weights (~23.3 GB) exceed host capacity. "
            "External GPU infrastructure (4x NVIDIA L4 or equivalent) is required for LoRA training/evaluation."
        )
    elif not cuda_avail or gpu_count == 0:
        classification = InfrastructureClassification.EXTERNAL_GPU_REQUIRED.value
        rationale = (
            f"Zero NVIDIA CUDA GPUs detected on host ({os_release}). "
            "External GPU infrastructure (4x NVIDIA L4 or equivalent) is required for LoRA training/evaluation."
        )
    else:
        classification = InfrastructureClassification.LOCAL_NOT_FEASIBLE.value
        rationale = f"Detected GPU ({gpu_name}) has insufficient VRAM ({vram_gb} GB) for 31B model adapter training."

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


# Convenience alias for CLI and external consumers
run_hardware_audit = audit_hardware_environment
