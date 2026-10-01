"""Controlled LoRA Experiment Contract and No-Adapter Control Generator (Stage 37 Sections 14, 15, 17).

Generates the authoritative machine-readable contract for future Stage 39 execution:
- Baseline candidate (M0 root-only no-adapter baseline)
- Future candidate placeholder (L1 single-adapter)
- Strictly frozen invariant dimensions (P0, R0, T0, REC0, root_only, 9 tools, frozen skills)
- Exactly ONE primary training objective (OBJ-TOOL-DISCIPLINE)
- Causal ablation plan (A: no-adapter control vs. B: base + LoRA adapter)
- Formal gating criteria: validation improvement AND zero held-out regression AND zero collateral regressions
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from local.lora_opt.architecture_stability import (
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_R0_RETRIEVAL_POLICY_HASH,
    EXPECTED_REC0_RECOVERY_POLICY_HASH,
    EXPECTED_REPO_TRIAGE_SKILL_SHA256,
    EXPECTED_T0_TESTING_POLICY_HASH,
    EXPECTED_TEST_STRATEGY_SKILL_SHA256,
    EXPECTED_TOPOLOGY_ID,
)
from local.lora_opt.models import CandidateObjective, ControlledLoRAExperimentContract
from local.lora_opt.objectives import CANONICAL_CANDIDATE_OBJECTIVES
from local.lora_opt.tool_contracts import ToolContractAuditor


def create_experiment_contract(
    primary_objective: Optional[CandidateObjective] = None,
    repo_root: Optional[Path | str] = None,
) -> ControlledLoRAExperimentContract:
    """Builds the formal controlled experiment contract for future Stage 39 execution."""
    root = Path(repo_root).resolve() if repo_root else Path.cwd()
    tool_auditor = ToolContractAuditor(root)
    _, _, tool_hashes = tool_auditor.audit_tool_contracts()

    obj_name = primary_objective.objective_id if primary_objective else "OBJ-TOOL-DISCIPLINE"

    contract = ControlledLoRAExperimentContract(
        baseline_candidate="M0",
        candidate_id_placeholder="L1",
        model_id="gemma-4-31b-it-qat-w4a16-ct",
        adapter_role="ROOT_AGENT_ADAPTER",
        primary_objective=obj_name,
        training_data_source_placeholder="STAGE_38_TRAJECTORY_DATASET",
        training_data_hash_placeholder="PENDING_STAGE_38_CONSTRUCTION",
        train_split_placeholder="dev",
        validation_split_placeholder="validation",
        held_out_split="held_out",
        prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        skill_hashes={
            "test_strategy": EXPECTED_TEST_STRATEGY_SKILL_SHA256,
            "repo_triage": EXPECTED_REPO_TRIAGE_SKILL_SHA256,
        },
        tool_contract_hashes=tool_hashes,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology=EXPECTED_TOPOLOGY_ID,
        sampling_settings={
            "temperature": 0.2,
            "top_p": 0.95,
            "max_output_tokens": 16384,
            "thinking_config": {
                "thinking_level": "high",
                "thinking_budget": 4096,
                "include_thoughts": True,
            },
        },
        evaluation_protocol="CLEAN_COPY_EVALUATOR_PAIRED_COMPARISON",
        primary_metric="command_redundancy_count",
        secondary_metrics=[
            "task_success_rate",
            "target_failure_rate",
            "tool_call_count",
            "turn_count",
            "runtime_ms",
        ],
        cost_metrics=[
            "adapter_size_bytes",
            "training_hours_l4",
            "inference_latency_delta_ms",
        ],
        promotion_gate="VALIDATION_IMPROVEMENT_AND_NO_HELD_OUT_REGRESSION",
        stop_conditions=[
            "HELD_OUT_REGRESSION",
            "TOOL_SCHEMA_VIOLATION",
            "NON_TARGET_BEHAVIOR_COLLATERAL_DROP",
            "COLLATERAL_PASS_TO_FAIL_REGRESSION",
        ],
    )
    return contract


def save_experiment_contract(
    contract: ControlledLoRAExperimentContract,
    dest_path: Optional[Path | str] = None,
) -> Path:
    """Serializes the experiment contract to JSON."""
    p = (
        Path(dest_path)
        if dest_path
        else Path("experiments/lora/L0/experiment_contract.json")
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(contract.to_dict(), indent=2), encoding="utf-8")
    return p


def build_experiment_contract(
    repo_root: Optional[Path | str] = None,
    primary_obj: Optional[CandidateObjective] = None,
) -> ControlledLoRAExperimentContract:
    """Builds formal Stage 39 controlled experiment contract."""
    return create_experiment_contract(primary_objective=primary_obj, repo_root=repo_root)


def build_no_adapter_control(repo_root: Optional[Path | str] = None) -> Dict[str, Any]:
    """Generates explicit no-adapter control definition (Control A)."""
    root = Path(repo_root).resolve() if repo_root else Path.cwd()
    tool_auditor = ToolContractAuditor(root)
    _, _, tool_hashes = tool_auditor.audit_tool_contracts()
    return {
        "candidate_id": "M0",
        "description": "Frozen competition baseline without LoRA adapter",
        "model_id": "gemma-4-31b-it-qat-w4a16-ct",
        "prompt_hash": EXPECTED_P0_PROMPT_SHA256,
        "retrieval_version": "R0",
        "testing_version": "T0",
        "recovery_version": "REC0",
        "topology": EXPECTED_TOPOLOGY_ID,
        "adapter_enabled": False,
        "adapter_path": None,
        "adapter_hash": None,
        "tool_contract_hashes": tool_hashes,
        "sampling_settings": {
            "temperature": 0.2,
            "top_p": 0.95,
            "max_output_tokens": 16384,
        },
    }
