"""Invariance Verification Subsystem for Stage 39 LoRA Training (Section 14).

Verifies that the L1 candidate configuration strictly preserves all frozen baseline
system dimensions and only introduces the single approved LoRA adapter:
- Model identifier: gemma-4-31b-it-qat-w4a16-ct
- Root prompt: 2360d4bf...
- Tool contracts: 9 locked hashes
- Retrieval policy: R0
- Testing strategy: T0
- Recovery policy: REC0
- Multi-agent topology: root_only
- Benchmark split: held_out frozen
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.lora_train.errors import InvarianceViolationError
from local.lora_train.models import TrainingConfig

# Authoritative frozen dimensions established in Stage 37 & 38
FROZEN_BASELINE_DIMENSIONS = {
    "base_model": "gemma-4-31b-it-qat-w4a16-ct",
    "prompt_hash": "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
    "retrieval_version": "R0",
    "testing_version": "T0",
    "recovery_version": "REC0",
    "topology": "root_only",
    "objective_id": "OBJ-TOOL-DISCIPLINE",
}

FROZEN_TOOL_CONTRACT_HASHES = {
    "run_command": "d48386318ec0eee1fa585ca53d1d3a8cc04ec06cc9acb851229aa9258cb95d8a",
    "submit_patch": "7ad08c240566f903e9fbcc217fd1af8dbf4796019812be1857b4bba6c9cb9490",
    "get_status": "59d2bdd46f070c357aeba14267cad7f67a394758908eb2c41b6ed140dda0bfe1",
    "read_file": "7c1fc9cd8769c270c8a7895f4322304c09c0212bc515ff24c75e1a39e241cfdc",
    "edit_file": "700f0f4920bd2095d9179a5a743d6dee0ce6997258c7c2dbbb6916645fd7eb50",
    "write_file": "b27c17afe3d7d7ed78cdeebcfca97fe02d866bf885dd088fb760a6ec8daa5183",
    "get_code_neighbors": "ff0902e2aa436c0f62607e95f7e02c9b56f57dfed11579feb81714be2b24b865",
    "search_similar_code": "3e378d8d83a59d3e736b3113db12ddf8ba52d5df929bd16851be4146348e55d7",
    "get_code_subgraph": "48fae3adc006e8e811c1b7dff61e5fe10a83dabbc80ddfc3681d098431b6f784",
}


class InvarianceChecker:
    """Audits candidate LoRA training configurations against the frozen Stage 37 baseline."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()

    def check_invariance(self, config: TrainingConfig) -> tuple[bool, list[str]]:
        """Verifies that config matches all frozen dimensions.

        Returns:
            (is_invariant, list_of_violations)
        """
        violations: list[str] = []

        # 1. Base model check
        if config.base_model != FROZEN_BASELINE_DIMENSIONS["base_model"]:
            violations.append(
                f"Model mismatch: expected '{FROZEN_BASELINE_DIMENSIONS['base_model']}', got '{config.base_model}'"
            )

        # 2. Objective check
        if config.objective_id != FROZEN_BASELINE_DIMENSIONS["objective_id"]:
            violations.append(
                f"Objective mismatch: expected '{FROZEN_BASELINE_DIMENSIONS['objective_id']}', got '{config.objective_id}'"
            )

        # 3. Prompt hash check
        if config.prompt_hash != FROZEN_BASELINE_DIMENSIONS["prompt_hash"]:
            violations.append(
                f"Prompt hash mismatch: expected '{FROZEN_BASELINE_DIMENSIONS['prompt_hash']}', got '{config.prompt_hash}'"
            )

        # 4. Topology and sub-system version checks
        for key in ["retrieval_version", "testing_version", "recovery_version", "topology"]:
            expected_val = FROZEN_BASELINE_DIMENSIONS[key]
            actual_val = getattr(config, key, None)
            if actual_val != expected_val:
                violations.append(f"{key} mismatch: expected '{expected_val}', got '{actual_val}'")

        # 5. Tool contract hashes check
        if config.tool_contract_hashes:
            for tool_name, exp_hash in FROZEN_TOOL_CONTRACT_HASHES.items():
                act_hash = config.tool_contract_hashes.get(tool_name)
                if act_hash != exp_hash:
                    violations.append(
                        f"Tool contract hash mismatch for '{tool_name}': expected '{exp_hash}', got '{act_hash}'"
                    )

        is_invariant = len(violations) == 0
        return is_invariant, violations

    def enforce_invariance(self, config: TrainingConfig) -> None:
        """Enforces invariance, raising InvarianceViolationError if any mismatch is detected."""
        is_inv, violations = self.check_invariance(config)
        if not is_inv:
            raise InvarianceViolationError(violations)
