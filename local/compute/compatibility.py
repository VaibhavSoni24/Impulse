"""Experiment Environment Contract and Compatibility Evaluator (Section 12).

Evaluates whether an experiment can execute in a target compute environment
without altering the experiment definition.
"""

from __future__ import annotations

from typing import List

from local.compute.models import (
    EnvironmentClass,
    EnvironmentContract,
    HardwareProfile,
    SoftwareProfile,
)

# Experiments that strictly require CUDA GPU infrastructure
GPU_DEPENDENT_EXPERIMENTS = {
    "L1_TRAINING",
    "L1_ABLATION_LIVE",
    "MA1_EXECUTION",
    "GPU_BENCHMARK",
    "GEMMA_31B_INFERENCE",
}

# Experiments supported on local CPU
CPU_SUPPORTED_EXPERIMENTS = {
    "E0_PROMPT_WORK",
    "M0_VALIDATION",
    "COMPUTE_DIAGNOSTICS",
    "DRY_RUN",
    "STAGE42_AUDIT",
    "STAGE41_VERIFY",
    "STAGE40_VERIFY",
    "STAGE39_VERIFY",
    "PACKAGING_VERIFY",
    "BENCHMARK_ANALYSIS",
}


def evaluate_experiment_compatibility(
    experiment_id: str,
    hardware: HardwareProfile,
    software: SoftwareProfile,
) -> EnvironmentContract:
    """Evaluates compatibility and constructs the EnvironmentContract."""
    norm_exp_id = experiment_id.upper().strip()
    is_gpu_req = norm_exp_id in GPU_DEPENDENT_EXPERIMENTS

    actual_caps: List[str] = []
    if hardware.cuda_available:
        actual_caps.append("CUDA_ACCELERATION")
        if hardware.per_gpu_vram_gb:
            actual_caps.append(f"VRAM_{hardware.per_gpu_vram_gb}GB")
    else:
        actual_caps.append("CPU_EXECUTION")
        actual_caps.append("HOST_RAM_VALIDATION")

    # Add installed ML packages to actual capabilities
    for pkg, ver in software.packages.items():
        if ver is not None:
            actual_caps.append(f"{pkg}_{ver}")

    if is_gpu_req:
        required_capabilities = ["CUDA_ACCELERATION", "TORCH_GPU", "PEFT_RUNTIME"]
        required_gpu_memory = "UNKNOWN"  # Do not invent unverified VRAM limits
        required_cuda = True
        required_packages = ["torch", "transformers", "peft", "accelerate"]

        if not hardware.cuda_available:
            compatibility_status = "BLOCKED"
        else:
            # Check software dependencies
            missing = [pkg for pkg in required_packages if software.packages.get(pkg) is None]
            if missing:
                compatibility_status = "INCOMPATIBLE"
            else:
                compatibility_status = "READY"
    else:
        # CPU-compatible experiment
        required_capabilities = ["CPU_EXECUTION", "PYTHON_310"]
        required_gpu_memory = "0GB"
        required_cuda = False
        required_packages = ["pytest", "psutil"]

        compatibility_status = "READY"

    return EnvironmentContract(
        environment_id=f"ENV_{hardware.environment_class.value}_{hardware.os_name.upper()}",
        environment_class=hardware.environment_class.value,
        experiment_id=experiment_id,
        required_capabilities=required_capabilities,
        required_gpu_memory=required_gpu_memory,
        required_cuda=required_cuda,
        required_python=">=3.10",
        required_packages=required_packages,
        actual_capabilities=actual_caps,
        compatibility_status=compatibility_status,
    )
