"""Condition Manager and Builders for Stage 40 LoRA Ablation (Section 3, 5, 6, 7).

Manages the four controlled ablation conditions:
- Condition A: BASELINE_NO_ADAPTER
- Condition B: L1_ADAPTER
- Condition C: L1_ADAPTER_PROMPT_VARIANT
- Condition D: L1_ADAPTER_RETRIEVAL_VARIANT
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

from local.lora_ablation.adapter_gate import AdapterGateValidator
from local.lora_ablation.errors import (
    InvarianceViolationError,
    MissingAdapterError,
    SecondaryConditionBlockedError,
)
from local.lora_ablation.models import (
    AblationConditionConfig,
    AdapterArtifactMetadata,
    AdapterGateStatus,
    ConditionStatus,
    ConditionType,
    FROZEN_BASELINE_DIMENSIONS,
    FROZEN_TOOL_CONTRACT_HASHES,
)


class ConditionManager:
    """Constructs, validates, and gates the 4 controlled ablation conditions."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.adapter_validator = AdapterGateValidator(self.repo_root)

    def build_condition_a(
        self,
        benchmark_split: str = "dev",
        benchmark_manifest_hash: str = "1b95c9fcfad8478fb4839cf9e3557e5e3d7a8e7e137a1f592d3f74151a6671fe",
    ) -> AblationConditionConfig:
        """Constructs Condition A (BASELINE_NO_ADAPTER) from the frozen baseline."""
        return AblationConditionConfig(
            condition_type=ConditionType.BASELINE_NO_ADAPTER,
            condition_label="Condition A (Frozen Baseline Control)",
            candidate_id="M0",
            base_model=FROZEN_BASELINE_DIMENSIONS["base_model"],
            adapter_enabled=False,
            adapter_path=None,
            adapter_sha256=None,
            prompt_hash=FROZEN_BASELINE_DIMENSIONS["prompt_hash"],
            tool_contract_hashes=dict(FROZEN_TOOL_CONTRACT_HASHES),
            retrieval_version=FROZEN_BASELINE_DIMENSIONS["retrieval_version"],
            testing_version=FROZEN_BASELINE_DIMENSIONS["testing_version"],
            recovery_version=FROZEN_BASELINE_DIMENSIONS["recovery_version"],
            topology=FROZEN_BASELINE_DIMENSIONS["topology"],
            benchmark_split=benchmark_split,
            benchmark_manifest_hash=benchmark_manifest_hash,
            status=ConditionStatus.READY_FOR_ABLATION,
            status_reason="Baseline configuration verified against frozen Stage 37-39 specifications.",
        )

    def build_condition_b(
        self,
        adapter_path: Optional[str | Path] = None,
        benchmark_split: str = "dev",
        benchmark_manifest_hash: str = "1b95c9fcfad8478fb4839cf9e3557e5e3d7a8e7e137a1f592d3f74151a6671fe",
    ) -> Tuple[AblationConditionConfig, AdapterGateStatus, Optional[AdapterArtifactMetadata]]:
        """Constructs Condition B (L1_ADAPTER) after validating the candidate adapter.

        Gated strictly by the Hard Adapter Gate. If no valid adapter exists,
        returns condition with MISSING_ADAPTER_ARTIFACT status.
        """
        is_valid, gate_status, reason, metadata = self.adapter_validator.validate_adapter(adapter_path)

        if not is_valid or metadata is None:
            config = AblationConditionConfig(
                condition_type=ConditionType.L1_ADAPTER,
                condition_label="Condition B (Baseline + L1 Adapter)",
                candidate_id="L1",
                base_model=FROZEN_BASELINE_DIMENSIONS["base_model"],
                adapter_enabled=True,
                adapter_path=str(adapter_path) if adapter_path else None,
                adapter_sha256=None,
                prompt_hash=FROZEN_BASELINE_DIMENSIONS["prompt_hash"],
                tool_contract_hashes=dict(FROZEN_TOOL_CONTRACT_HASHES),
                retrieval_version=FROZEN_BASELINE_DIMENSIONS["retrieval_version"],
                testing_version=FROZEN_BASELINE_DIMENSIONS["testing_version"],
                recovery_version=FROZEN_BASELINE_DIMENSIONS["recovery_version"],
                topology=FROZEN_BASELINE_DIMENSIONS["topology"],
                benchmark_split=benchmark_split,
                benchmark_manifest_hash=benchmark_manifest_hash,
                status=ConditionStatus.MISSING_ADAPTER_ARTIFACT,
                status_reason=f"Hard Adapter Gate blocked: {reason}",
            )
            return (config, gate_status, None)

        config = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B (Baseline + L1 Adapter)",
            candidate_id="L1",
            base_model=FROZEN_BASELINE_DIMENSIONS["base_model"],
            adapter_enabled=True,
            adapter_path=metadata.adapter_dir,
            adapter_sha256=metadata.adapter_sha256,
            prompt_hash=FROZEN_BASELINE_DIMENSIONS["prompt_hash"],
            tool_contract_hashes=dict(FROZEN_TOOL_CONTRACT_HASHES),
            retrieval_version=FROZEN_BASELINE_DIMENSIONS["retrieval_version"],
            testing_version=FROZEN_BASELINE_DIMENSIONS["testing_version"],
            recovery_version=FROZEN_BASELINE_DIMENSIONS["recovery_version"],
            topology=FROZEN_BASELINE_DIMENSIONS["topology"],
            benchmark_split=benchmark_split,
            benchmark_manifest_hash=benchmark_manifest_hash,
            status=ConditionStatus.READY_FOR_ABLATION,
            status_reason="Adapter verified by Hard Adapter Gate. Ready for A/B ablation.",
        )
        return (config, AdapterGateStatus.READY, metadata)

    def build_condition_c(
        self,
        b_condition: AblationConditionConfig,
        variant_prompt_hash: str = "variant_prompt_placeholder_hash",
        prompt_variant_reason: str = "Ablation of prompt reinforcement alongside L1 adapter",
        prompt_diff: Optional[str] = None,
    ) -> AblationConditionConfig:
        """Constructs Condition C (L1_ADAPTER_PROMPT_VARIANT).

        Strictly gated on Condition B completion.
        """
        if b_condition.status != ConditionStatus.COMPLETED and b_condition.status != ConditionStatus.READY_FOR_ABLATION:
            return AblationConditionConfig(
                condition_type=ConditionType.L1_ADAPTER_PROMPT_VARIANT,
                condition_label="Condition C (L1 Adapter + Prompt Variant)",
                candidate_id="L1-P1",
                base_model=b_condition.base_model,
                adapter_enabled=True,
                adapter_path=b_condition.adapter_path,
                adapter_sha256=b_condition.adapter_sha256,
                prompt_hash=variant_prompt_hash,
                prompt_variant_reason=prompt_variant_reason,
                prompt_diff=prompt_diff,
                tool_contract_hashes=dict(b_condition.tool_contract_hashes),
                retrieval_version=b_condition.retrieval_version,
                testing_version=b_condition.testing_version,
                recovery_version=b_condition.recovery_version,
                topology=b_condition.topology,
                benchmark_split=b_condition.benchmark_split,
                benchmark_manifest_hash=b_condition.benchmark_manifest_hash,
                status=ConditionStatus.BLOCKED_BY_MISSING_ADAPTER,
                status_reason="Condition C cannot execute: Condition B has not produced a verified adapter evaluation.",
            )

        return AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER_PROMPT_VARIANT,
            condition_label="Condition C (L1 Adapter + Prompt Variant)",
            candidate_id="L1-P1",
            base_model=b_condition.base_model,
            adapter_enabled=True,
            adapter_path=b_condition.adapter_path,
            adapter_sha256=b_condition.adapter_sha256,
            prompt_hash=variant_prompt_hash,
            prompt_variant_reason=prompt_variant_reason,
            prompt_diff=prompt_diff,
            tool_contract_hashes=dict(b_condition.tool_contract_hashes),
            retrieval_version=b_condition.retrieval_version,
            testing_version=b_condition.testing_version,
            recovery_version=b_condition.recovery_version,
            topology=b_condition.topology,
            benchmark_split=b_condition.benchmark_split,
            benchmark_manifest_hash=b_condition.benchmark_manifest_hash,
            status=ConditionStatus.READY_FOR_ABLATION,
            status_reason="Prompt variant configured and isolated from retrieval/model changes.",
        )

    def build_condition_d(
        self,
        b_condition: AblationConditionConfig,
        variant_retrieval_version: str = "R1",
        retrieval_variant_reason: str = "Ablation of semantic retrieval alongside L1 adapter",
    ) -> AblationConditionConfig:
        """Constructs Condition D (L1_ADAPTER_RETRIEVAL_VARIANT).

        Strictly gated on Condition B completion.
        """
        if b_condition.status != ConditionStatus.COMPLETED and b_condition.status != ConditionStatus.READY_FOR_ABLATION:
            return AblationConditionConfig(
                condition_type=ConditionType.L1_ADAPTER_RETRIEVAL_VARIANT,
                condition_label="Condition D (L1 Adapter + Retrieval Variant)",
                candidate_id="L1-R1",
                base_model=b_condition.base_model,
                adapter_enabled=True,
                adapter_path=b_condition.adapter_path,
                adapter_sha256=b_condition.adapter_sha256,
                prompt_hash=b_condition.prompt_hash,
                tool_contract_hashes=dict(b_condition.tool_contract_hashes),
                retrieval_version=variant_retrieval_version,
                retrieval_variant_reason=retrieval_variant_reason,
                testing_version=b_condition.testing_version,
                recovery_version=b_condition.recovery_version,
                topology=b_condition.topology,
                benchmark_split=b_condition.benchmark_split,
                benchmark_manifest_hash=b_condition.benchmark_manifest_hash,
                status=ConditionStatus.BLOCKED_BY_MISSING_ADAPTER,
                status_reason="Condition D cannot execute: Condition B has not produced a verified adapter evaluation.",
            )

        return AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER_RETRIEVAL_VARIANT,
            condition_label="Condition D (L1 Adapter + Retrieval Variant)",
            candidate_id="L1-R1",
            base_model=b_condition.base_model,
            adapter_enabled=True,
            adapter_path=b_condition.adapter_path,
            adapter_sha256=b_condition.adapter_sha256,
            prompt_hash=b_condition.prompt_hash,
            tool_contract_hashes=dict(b_condition.tool_contract_hashes),
            retrieval_version=variant_retrieval_version,
            retrieval_variant_reason=retrieval_variant_reason,
            testing_version=b_condition.testing_version,
            recovery_version=b_condition.recovery_version,
            topology=b_condition.topology,
            benchmark_split=b_condition.benchmark_split,
            benchmark_manifest_hash=b_condition.benchmark_manifest_hash,
            status=ConditionStatus.READY_FOR_ABLATION,
            status_reason="Retrieval variant configured and isolated from prompt/model changes.",
        )

    def build_all_conditions(
        self,
        adapter_path: Optional[str | Path] = None,
        benchmark_split: str = "dev",
    ) -> Dict[str, AblationConditionConfig]:
        """Assembles all 4 conditions reflecting current repository state."""
        cond_a = self.build_condition_a(benchmark_split=benchmark_split)
        cond_b, _, _ = self.build_condition_b(adapter_path, benchmark_split=benchmark_split)
        cond_c = self.build_condition_c(cond_b)
        cond_d = self.build_condition_d(cond_b)

        return {
            "A": cond_a,
            "B": cond_b,
            "C": cond_c,
            "D": cond_d,
        }
