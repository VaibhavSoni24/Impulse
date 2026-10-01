"""Hardware Discovery and Hardware Profile Auditor for Stage 42 (Section 8).

Validates and observes:
- OS name, release, architecture, and Python version
- CPU model and core counts (physical and logical)
- Host RAM total and available
- Available disk space
- GPU count, model, VRAM, driver version, and CUDA availability
- Disallows reporting integrated graphics (Intel Iris Xe, UHD, etc.) as CUDA devices.
- Observes without hardcoding whether the host is LOCAL_CPU, LOCAL_GPU, KAGGLE_FREE_GPU, or EXTERNAL_LINUX_GPU.
"""

from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Optional, Tuple

from local.compute.models import (
    CUDACapability,
    EnvironmentClass,
    HardwareProfile,
)


def _detect_cpu_model() -> str:
    """Attempts platform-native detection of the CPU model name."""
    system = platform.system()
    try:
        if system == "Windows":
            # Try CIM Win32_Processor
            res = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip().splitlines()[0].strip()
        elif system == "Linux" and os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
        elif system == "Darwin":
            res = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
    except Exception:
        pass

    # Fallback to standard platform processor string
    return platform.processor() or "Unknown CPU"


def _probe_nvidia_smi() -> Tuple[bool, Optional[str], int, Optional[float], Optional[str], Optional[str]]:
    """Probes nvidia-smi for NVIDIA GPUs, VRAM, driver version, and CUDA version."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            gpu_count = len(lines)
            first_line = lines[0].split(",")
            gpu_name = first_line[0].strip()
            vram_mb = float(first_line[1].strip())
            vram_gb = round(vram_mb / 1024.0, 2)
            driver_ver = first_line[2].strip() if len(first_line) > 2 else None

            # Probe CUDA version from nvidia-smi header or nvcc
            cuda_ver = None
            try:
                header_res = subprocess.run(
                    ["nvidia-smi"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if header_res.returncode == 0:
                    match = re.search(r"CUDA Version:\s*(\d+\.\d+)", header_res.stdout)
                    if match:
                        cuda_ver = match.group(1).strip()
            except Exception:
                pass

            return True, gpu_name, gpu_count, vram_gb, driver_ver, cuda_ver
    except Exception:
        pass

    return False, None, 0, None, None, None


def _probe_windows_video_controllers() -> Tuple[Optional[str], int, bool, Optional[str]]:
    """Probes Windows CIM for video controllers, identifying integrated graphics."""
    if platform.system() != "Windows":
        return None, 0, False, None

    try:
        res = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            import json
            try:
                data = json.loads(res.stdout.strip())
                if isinstance(data, dict):
                    controllers = [data]
                elif isinstance(data, list):
                    controllers = data
                else:
                    controllers = []
            except Exception:
                controllers = []

            if controllers:
                names = [c.get("Name", "") for c in controllers if c.get("Name")]
                first_name = names[0] if names else None
                driver_ver = controllers[0].get("DriverVersion") if controllers else None

                # Check if integrated graphics
                lower_names = " ".join(names).lower()
                is_integrated = any(
                    ig in lower_names
                    for ig in ["intel", "iris", "uhd", "vega", "radeon(tm)", "basic render"]
                )
                return first_name, len(names), is_integrated, driver_ver
    except Exception:
        pass

    return None, 0, False, None


def detect_hardware(repo_root: Optional[Path] = None) -> HardwareProfile:
    """Detects and returns complete, verified host hardware profile."""
    os_name = platform.system()
    os_release = platform.platform()
    architecture = platform.machine()
    py_ver = sys.version.split()[0]

    # CPU
    cpu_model = _detect_cpu_model()
    cpu_logical = os.cpu_count() or 1
    cpu_physical = cpu_logical
    try:
        import psutil
        phys = psutil.cpu_count(logical=False)
        if phys:
            cpu_physical = phys
    except Exception:
        pass

    # RAM
    total_ram_gb = 0.0
    available_ram_gb = 0.0
    try:
        import psutil
        vmem = psutil.virtual_memory()
        total_ram_gb = round(vmem.total / (1024**3), 2)
        available_ram_gb = round(vmem.available / (1024**3), 2)
    except Exception:
        pass

    # Disk
    root_path = repo_root or Path(".")
    try:
        free_disk_gb = round(shutil.disk_usage(root_path).free / (1024**3), 2)
    except Exception:
        free_disk_gb = 0.0

    # Probe NVIDIA GPUs first via nvidia-smi
    cuda_avail, gpu_name, gpu_count, vram_gb, driver_ver, cuda_ver = _probe_nvidia_smi()
    is_integrated = False

    if not cuda_avail:
        # Check non-NVIDIA or integrated GPUs (e.g. Windows CIM)
        win_name, win_count, win_integrated, win_driver = _probe_windows_video_controllers()
        if win_name:
            gpu_name = win_name
            gpu_count = win_count
            is_integrated = win_integrated
            driver_ver = win_driver
            # Integrated graphics must NEVER be reported as CUDA GPUs
            cuda_avail = False

    # Determine environment class and classification
    is_kaggle = os.path.exists("/kaggle") or bool(os.environ.get("KAGGLE_KERNEL_RUN_TYPE"))
    if is_kaggle:
        env_class = EnvironmentClass.KAGGLE_FREE_GPU
    elif os_name == "Linux" and cuda_avail:
        env_class = EnvironmentClass.EXTERNAL_LINUX_GPU
    elif cuda_avail:
        env_class = EnvironmentClass.LOCAL_GPU
    else:
        env_class = EnvironmentClass.LOCAL_CPU

    classification = (
        CUDACapability.CUDA_AVAILABLE.value if cuda_avail
        else CUDACapability.NO_CUDA_GPU.value
    )

    return HardwareProfile(
        os_name=os_name,
        os_release=os_release,
        architecture=architecture,
        python_version=py_ver,
        cpu_model=cpu_model,
        cpu_count_physical=cpu_physical,
        cpu_count_logical=cpu_logical,
        total_ram_gb=total_ram_gb,
        available_ram_gb=available_ram_gb,
        free_disk_gb=free_disk_gb,
        gpu_count=gpu_count,
        gpu_model=gpu_name,
        per_gpu_vram_gb=vram_gb,
        cuda_available=cuda_avail,
        cuda_version=cuda_ver,
        driver_version=driver_ver,
        classification=classification,
        is_integrated_gpu=is_integrated,
        environment_class=env_class,
    )
