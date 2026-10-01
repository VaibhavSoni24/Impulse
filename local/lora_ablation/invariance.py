"""Invariance Verification Subsystem for Stage 40 LoRA Ablation (Section 6, 7).

Verifies that the primary causal comparison (Condition A vs Condition B) holds
all major system dimensions strictly constant and differs ONLY by adapter reference:
- Model identifier: gemma-4-31b-it-qat-w4a16-ct
- Root prompt: 2360d4bf...
- Tool contracts: 9 locked hashes
- Retrieval policy: R0
- Testing strategy: T0
- Recovery policy: REC0
- Multi-agent topology: root_only
- Benchmark split: identical tasks and manifest hash
- Sampling settings: identical

Also verifies that secondary variants (C and D) change exactly one controlled dimension.
"""

from __future__ import annotations

from typing import List, Tuple

from local.lora_ablation.errors import InvarianceViolationError
from local.lora_ablation.models import (
    AblationConditionConfig,
    ConditionType,
    FROZEN_BASELINE_DIMENSIONS,
    FROZEN_TOOL_CONTRACT_HASHES,
)


class AblationInvarianceChecker:
    """Verifies that ablation conditions uphold strict scientific control and causal interpretability."""

    def check_baseline_invariance(self, config: AblationConditionConfig) -> Tuple[bool, List[str]]:
        """Verifies that Condition A matches all frozen Stage 37-39 baseline dimensions."""
        violations: List[str] = []

        if config.base_model != FROZEN_BASELINE_DIMENSIONS["base_model"]:
            violations.append(
                f"Base model '{config.base_model}' != frozen '{FROZEN_BASELINE_DIMENSIONS['base_model']}'"
            )

        if config.prompt_hash != FROZEN_BASELINE_DIMENSIONS["prompt_hash"]:
            violations.append(
                f"Prompt hash '{config.prompt_hash}' != frozen '{FROZEN_BASELINE_DIMENSIONS['prompt_hash']}'"
            )

        if config.retrieval_version != FROZEN_BASELINE_DIMENSIONS["retrieval_version"]:
            violations.append(
                f"Retrieval version '{config.retrieval_version}' != frozen '{FROZEN_BASELINE_DIMENSIONS['retrieval_version']}'"
            )

        if config.testing_version != FROZEN_BASELINE_DIMENSIONS["testing_version"]:
            violations.append(
                f"Testing version '{config.testing_version}' != frozen '{FROZEN_BASELINE_DIMENSIONS['testing_version']}'"
            )

        if config.recovery_version != FROZEN_BASELINE_DIMENSIONS["recovery_version"]:
            violations.append(
                f"Recovery version '{config.recovery_version}' != frozen '{FROZEN_BASELINE_DIMENSIONS['recovery_version']}'"
            )

        if config.topology != FROZEN_BASELINE_DIMENSIONS["topology"]:
            violations.append(
                f"Topology '{config.topology}' != frozen '{FROZEN_BASELINE_DIMENSIONS['topology']}'"
            )

        if config.adapter_enabled:
            violations.append("Condition A (BASELINE_NO_ADAPTER) must have adapter_enabled == False")

        # Check tool contracts
        for tool_name, expected_hash in FROZEN_TOOL_CONTRACT_HASHES.items():
            actual_hash = config.tool_contract_hashes.get(tool_name)
            if actual_hash != expected_hash:
                violations.append(
                    f"Tool contract for '{tool_name}' hash '{actual_hash}' != frozen '{expected_hash}'"
                )

        return (len(violations) == 0, violations)

    def check_primary_ablation_pair(
        self,
        cond_a: AblationConditionConfig,
        cond_b: AblationConditionConfig,
    ) -> Tuple[bool, List[str]]:
        """Verifies that Condition B differs from Condition A ONLY by the LoRA adapter.

        All other dimensions (model, prompt, tools, retrieval, testing, recovery,
        topology, benchmark split, sampling settings) must be identical.
        """
        violations: List[str] = []

        if cond_a.condition_type != ConditionType.BASELINE_NO_ADAPTER:
            violations.append(f"cond_a must be BASELINE_NO_ADAPTER, got {cond_a.condition_type}")

        if cond_b.condition_type != ConditionType.L1_ADAPTER:
            violations.append(f"cond_b must be L1_ADAPTER, got {cond_b.condition_type}")

        # Model must be identical
        if cond_a.base_model != cond_b.base_model:
            violations.append(
                f"Primary comparison model mismatch: A has '{cond_a.base_model}', B has '{cond_b.base_model}'"
            )

        # Root prompt must be identical
        if cond_a.prompt_hash != cond_b.prompt_hash:
            violations.append(
                f"Primary comparison prompt mismatch: A has '{cond_a.prompt_hash}', B has '{cond_b.prompt_hash}'"
            )

        # Retrieval must be identical
        if cond_a.retrieval_version != cond_b.retrieval_version:
            violations.append(
                f"Primary comparison retrieval mismatch: A has '{cond_a.retrieval_version}', B has '{cond_b.retrieval_version}'"
            )

        # Testing strategy must be identical
        if cond_a.testing_version != cond_b.testing_version:
            violations.append(
                f"Primary comparison testing mismatch: A has '{cond_a.testing_version}', B has '{cond_b.testing_version}'"
            )

        # Recovery policy must be identical
        if cond_a.recovery_version != cond_b.recovery_version:
            violations.append(
                f"Primary comparison recovery mismatch: A has '{cond_a.recovery_version}', B has '{cond_b.recovery_version}'"
            )

        # Topology must be identical
        if cond_a.topology != cond_b.topology:
            violations.append(
                f"Primary comparison topology mismatch: A has '{cond_a.topology}', B has '{cond_b.topology}'"
            )

        # Benchmark split must be identical
        if cond_a.benchmark_split != cond_b.benchmark_split:
            violations.append(
                f"Primary comparison split mismatch: A has '{cond_a.benchmark_split}', B has '{cond_b.benchmark_split}'"
            )

        if cond_a.benchmark_manifest_hash != cond_b.benchmark_manifest_hash:
            violations.append(
                f"Primary comparison benchmark manifest mismatch: A has '{cond_a.benchmark_manifest_hash}', B has '{cond_b.benchmark_manifest_hash}'"
            )

        # Tool contracts must be identical
        for tool_name, a_hash in cond_a.tool_contract_hashes.items():
            b_hash = cond_b.tool_contract_hashes.get(tool_name)
            if a_hash != b_hash:
                violations.append(
                    f"Tool contract for '{tool_name}' differs: A has '{a_hash}', B has '{b_hash}'"
                )

        # Sampling settings must be identical
        if cond_a.sampling_settings != cond_b.sampling_settings:
            violations.append(
                f"Sampling settings differ: A has '{cond_a.sampling_settings}', B has '{cond_b.sampling_settings}'"
            )

        # Adapter condition checks: A has no adapter, B has adapter
        if cond_a.adapter_enabled:
            violations.append("Condition A must have adapter_enabled == False")

        if not cond_b.adapter_enabled:
            violations.append("Condition B must have adapter_enabled == True")

        if not cond_b.adapter_path:
            violations.append("Condition B must specify an adapter_path")

        return (len(violations) == 0, violations)

    def check_prompt_variant_pair(
        self,
        cond_b: AblationConditionConfig,
        cond_c: AblationConditionConfig,
    ) -> Tuple[bool, List[str]]:
        """Verifies that Condition C differs from Condition B ONLY by prompt."""
        violations: List[str] = []

        if cond_c.condition_type != ConditionType.L1_ADAPTER_PROMPT_VARIANT:
            violations.append(f"cond_c must be L1_ADAPTER_PROMPT_VARIANT, got {cond_c.condition_type}")

        # Adapter must be identical
        if cond_b.adapter_path != cond_c.adapter_path or cond_b.adapter_sha256 != cond_c.adapter_sha256:
            violations.append("Condition C must use the identical adapter to Condition B")

        # Invariant dimensions
        if cond_b.base_model != cond_c.base_model:
            violations.append("Model cannot differ between B and C")
        if cond_b.retrieval_version != cond_c.retrieval_version:
            violations.append("Retrieval cannot differ between B and C")
        if cond_b.testing_version != cond_c.testing_version:
            violations.append("Testing strategy cannot differ between B and C")
        if cond_b.recovery_version != cond_c.recovery_version:
            violations.append("Recovery policy cannot differ between B and C")
        if cond_b.topology != cond_c.topology:
            violations.append("Topology cannot differ between B and C")
        if cond_b.tool_contract_hashes != cond_c.tool_contract_hashes:
            violations.append("Tool contracts cannot differ between B and C")

        # Prompt MUST differ and reason MUST be documented
        if cond_b.prompt_hash == cond_c.prompt_hash:
            violations.append("Condition C must have a distinct prompt hash from Condition B")
        if not cond_c.prompt_variant_reason:
            violations.append("Condition C must document prompt_variant_reason")

        return (len(violations) == 0, violations)

    def check_retrieval_variant_pair(
        self,
        cond_b: AblationConditionConfig,
        cond_d: AblationConditionConfig,
    ) -> Tuple[bool, List[str]]:
        """Verifies that Condition D differs from Condition B ONLY by retrieval configuration."""
        violations: List[str] = []

        if cond_d.condition_type != ConditionType.L1_ADAPTER_RETRIEVAL_VARIANT:
            violations.append(f"cond_d must be L1_ADAPTER_RETRIEVAL_VARIANT, got {cond_d.condition_type}")

        # Adapter must be identical
        if cond_b.adapter_path != cond_d.adapter_path or cond_b.adapter_sha256 != cond_d.adapter_sha256:
            violations.append("Condition D must use the identical adapter to Condition B")

        # Invariant dimensions
        if cond_b.base_model != cond_d.base_model:
            violations.append("Model cannot differ between B and D")
        if cond_b.prompt_hash != cond_d.prompt_hash:
            violations.append("Prompt cannot differ between B and D")
        if cond_b.testing_version != cond_d.testing_version:
            violations.append("Testing strategy cannot differ between B and D")
        if cond_b.recovery_version != cond_d.recovery_version:
            violations.append("Recovery policy cannot differ between B and D")
        if cond_b.topology != cond_d.topology:
            violations.append("Topology cannot differ between B and D")
        if cond_b.tool_contract_hashes != cond_d.tool_contract_hashes:
            violations.append("Tool contracts cannot differ between B and D")

        # Retrieval MUST differ and reason MUST be documented
        if cond_b.retrieval_version == cond_d.retrieval_version:
            violations.append("Condition D must have a distinct retrieval version from Condition B")
        if not cond_d.retrieval_variant_reason:
            violations.append("Condition D must document retrieval_variant_reason")

        return (len(violations) == 0, violations)
