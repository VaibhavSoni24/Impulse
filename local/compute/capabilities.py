"""Capability Matrix for Stage 42 Free Compute Layer (Section 11).

Distinguishes:
- SUPPORTED_BY_DESIGN: Capabilities engineered and architected into IMPULSE.
- ACTUALLY_VERIFIED: Capabilities verified by concrete execution in the environment.
- BLOCKED: Capabilities that cannot execute in the environment (e.g. GPU_REQUIRED).
"""

from __future__ import annotations

from typing import Dict, Optional

from local.compute.models import (
    CapabilityItem,
    CapabilityMatrix,
    EnvironmentClass,
    VerificationStatus,
)


def get_capability_matrix(env_class: Optional[EnvironmentClass] = None) -> CapabilityMatrix:
    """Builds the machine-readable capability matrix for the specified or detected environment."""
    target_env = env_class or EnvironmentClass.LOCAL_CPU

    capabilities: Dict[str, CapabilityItem] = {}

    if target_env == EnvironmentClass.LOCAL_CPU:
        # All 14 local CPU responsibilities specified in Section 5
        capabilities["prompt_validation"] = CapabilityItem(
            name="prompt_validation",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Prompt templates and schema validation execute locally without GPU.",
        )
        capabilities["config_validation"] = CapabilityItem(
            name="config_validation",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="YAML and JSON agent configurations verified via schema validators.",
        )
        capabilities["manifest_generation"] = CapabilityItem(
            name="manifest_generation",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Experiment manifests and condition records generated deterministically.",
        )
        capabilities["benchmark_analysis"] = CapabilityItem(
            name="benchmark_analysis",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Splits, task distributions, and evaluation database queries run locally.",
        )
        capabilities["failure_analysis"] = CapabilityItem(
            name="failure_analysis",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="FDD clustering, taxonomy classification, and dashboards run locally.",
        )
        capabilities["dataset_validation"] = CapabilityItem(
            name="dataset_validation",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Dataset gate, leakage checks, and provenance verification run on CPU.",
        )
        capabilities["report_generation"] = CapabilityItem(
            name="report_generation",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Authoritative markdown and JSON audit reports generated locally.",
        )
        capabilities["unit_tests"] = CapabilityItem(
            name="unit_tests",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Unit tests execute with zero GPU dependence.",
        )
        capabilities["regression_tests"] = CapabilityItem(
            name="regression_tests",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Full regression suites across Stages 24-41 pass on CPU.",
        )
        capabilities["package_validation"] = CapabilityItem(
            name="package_validation",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Submission packaging checks and M0-M5 validations pass on CPU.",
        )
        capabilities["deterministic_zip_generation"] = CapabilityItem(
            name="deterministic_zip_generation",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Deterministic submission packaging supported without GPU.",
        )
        capabilities["hash_generation"] = CapabilityItem(
            name="hash_generation",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="SHA-256 fingerprinting and artifact verification run locally.",
        )
        capabilities["training_dry_run"] = CapabilityItem(
            name="training_dry_run",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Training pipeline dry runs and invariance checks run on CPU.",
        )
        capabilities["ablation_dry_run"] = CapabilityItem(
            name="ablation_dry_run",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Ablation framework dry runs and condition checks run on CPU.",
        )
        capabilities["compute_environment_diagnostics"] = CapabilityItem(
            name="compute_environment_diagnostics",
            supported=True,
            verified_status=VerificationStatus.ACTUALLY_VERIFIED.value,
            notes="Hardware discovery and software auditing execute locally.",
        )

        # GPU-dependent capabilities: strictly BLOCKED on LOCAL_CPU
        capabilities["gemma_31b_inference"] = CapabilityItem(
            name="gemma_31b_inference",
            supported=False,
            verified_status=VerificationStatus.BLOCKED.value,
            notes="GPU_REQUIRED: 23.3 GB model weights exceed local host VRAM capacity.",
        )
        capabilities["lora_training"] = CapabilityItem(
            name="lora_training",
            supported=False,
            verified_status=VerificationStatus.BLOCKED.value,
            notes="GPU_REQUIRED: PEFT training requires multi-GPU CUDA infrastructure.",
        )
        capabilities["adapter_inference"] = CapabilityItem(
            name="adapter_inference",
            supported=False,
            verified_status=VerificationStatus.BLOCKED.value,
            notes="GPU_REQUIRED: Model adapter evaluation requires GPU runtime.",
        )
        capabilities["multi_adapter_inference"] = CapabilityItem(
            name="multi_adapter_inference",
            supported=False,
            verified_status=VerificationStatus.BLOCKED.value,
            notes="GPU_REQUIRED: Multi-adapter routing evaluation requires GPU runtime.",
        )

    elif target_env == EnvironmentClass.KAGGLE_FREE_GPU:
        capabilities["configuration_supported"] = CapabilityItem(
            name="configuration_supported",
            supported=True,
            verified_status=VerificationStatus.SUPPORTED_BY_DESIGN.value,
            notes="Kaggle notebook architecture is supported by design.",
        )
        capabilities["actual_runtime_verified"] = CapabilityItem(
            name="actual_runtime_verified",
            supported=False,
            verified_status=VerificationStatus.NOT_VERIFIED.value,
            notes="No external Kaggle execution has been performed in this workspace.",
        )
        capabilities["p100_support"] = CapabilityItem(
            name="p100_support",
            supported=True,
            verified_status=VerificationStatus.SUPPORTED_BY_DESIGN.value,
            notes="Free single P100 (16GB VRAM) profile supported by design.",
        )
        capabilities["t4_dual_support"] = CapabilityItem(
            name="t4_dual_support",
            supported=True,
            verified_status=VerificationStatus.SUPPORTED_BY_DESIGN.value,
            notes="Free dual T4 (2x 15GB VRAM) profile supported by design.",
        )

    elif target_env == EnvironmentClass.EXTERNAL_LINUX_GPU:
        capabilities["configuration_supported"] = CapabilityItem(
            name="configuration_supported",
            supported=True,
            verified_status=VerificationStatus.SUPPORTED_BY_DESIGN.value,
            notes="External Linux GPU architecture supported by design.",
        )
        capabilities["actual_runtime_verified"] = CapabilityItem(
            name="actual_runtime_verified",
            supported=False,
            verified_status=VerificationStatus.NOT_VERIFIED.value,
            notes="No external Linux GPU execution has been performed in this workspace.",
        )
        capabilities["l4_quad_support"] = CapabilityItem(
            name="l4_quad_support",
            supported=True,
            verified_status=VerificationStatus.SUPPORTED_BY_DESIGN.value,
            notes="Multi-L4 (4x 24GB VRAM) training profile supported by design.",
        )
        capabilities["a100_support"] = CapabilityItem(
            name="a100_support",
            supported=True,
            verified_status=VerificationStatus.SUPPORTED_BY_DESIGN.value,
            notes="A100 (40GB/80GB VRAM) training profile supported by design.",
        )

    else:
        capabilities["unknown_environment"] = CapabilityItem(
            name="unknown_environment",
            supported=False,
            verified_status=VerificationStatus.NOT_VERIFIED.value,
            notes="Environment class not classified.",
        )

    return CapabilityMatrix(
        environment_class=target_env.value,
        capabilities=capabilities,
    )
