"""Invariant checkers for UNREPRESENTED_BLOCKED_FAILURE regressions (Stage 45 Phase 3).

Covers:
- REG-BLOCKED-001: 31B reasoning degradation under long context (>32k tokens).
- REG-BLOCKED-002: Kaggle container air-gapped network isolation timeout.

These failure modes are documented conceptually and historically in IMPULSE development,
but lack local CPU execution artifacts. They are preserved as honest BLOCKED records
and must never be fabricated or reported as PASS on local CPU.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from local.compute.hardware import detect_hardware
from local.compute.models import EnvironmentClass


def check_long_context_degradation_blocked() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-BLOCKED-001: Honest BLOCKED assessment for 31B long-context reasoning degradation."""
    hw = detect_hardware()

    # If running on local CPU without CUDA or model weights, execution is BLOCKED
    if hw.environment_class == EnvironmentClass.LOCAL_CPU or not hw.cuda_available:
        return (
            False,
            f"BLOCKED: Host environment ({hw.environment_class.value}) lacks Gemma 4 31B weights and CUDA GPU capacity; "
            "live long-context reasoning evaluation requires verified cluster/GPU execution.",
            {"environment_class": hw.environment_class.value, "blocked_by_hardware": True},
        )

    # In a real GPU cluster environment with live 31B model, this would execute the context benchmark
    return (
        False,
        "BLOCKED: External 31B inference cluster connection not established.",
        {"environment_class": hw.environment_class.value, "blocked_by_hardware": False},
    )


def check_kaggle_network_isolation_blocked() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-BLOCKED-002: Honest BLOCKED assessment for Kaggle air-gapped network isolation timeout."""
    hw = detect_hardware()

    # Local workstation is not a Kaggle competition sandbox container
    if hw.environment_class != EnvironmentClass.KAGGLE_FREE_GPU:
        return (
            False,
            f"BLOCKED: Current host ({hw.environment_class.value}) is not an active Kaggle evaluation container; "
            "air-gapped network isolation and dependency timeout reproduction requires live container runtime.",
            {"environment_class": hw.environment_class.value, "is_kaggle_container": False},
        )

    return (
        False,
        "BLOCKED: Live Kaggle container execution not active.",
        {"environment_class": hw.environment_class.value, "is_kaggle_container": True},
    )
