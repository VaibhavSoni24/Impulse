"""IMPULSE Stage 37: LoRA Feasibility / Readiness Study (L0) Package.

This package provides deterministic baseline auditing, benchmark stability
verification, failure taxonomy readiness analysis, objective candidate selection,
and controlled experiment contracting for LoRA studies.
"""

from local.lora_opt.models import (
    L0Decision,
    ReadinessDimensionStatus,
    BenchmarkStabilityStatus,
    InfrastructureClassification,
    ObjectiveStatus,
    ToolContractStatus,
    ToolContractRecord,
    CandidateObjective,
    HardwareAuditReport,
    ArchitectureStabilityReport,
    BenchmarkStabilityReport,
    FailureCategoryAudit,
    ControlledLoRAExperimentContract,
    BaselineSnapshot,
    L0Manifest,
    PromptStabilityReport,
)
from local.lora_opt.tool_contracts import (
    get_competition_tool_contracts,
    verify_tool_contracts,
)
from local.lora_opt.hardware_audit import run_hardware_audit
from local.lora_opt.prompt_stability import verify_root_prompt_stability
from local.lora_opt.benchmark_stability import verify_benchmark_stability
from local.lora_opt.failure_readiness import audit_failure_taxonomy
from local.lora_opt.objectives import (
    get_candidate_objectives,
    select_objectives,
)
from local.lora_opt.architecture_stability import verify_architecture_stability
from local.lora_opt.baseline import capture_baseline_snapshot
from local.lora_opt.experiment_contract import (
    build_experiment_contract,
    build_no_adapter_control,
)
from local.lora_opt.reporting import (
    determine_l0_decision,
    build_l0_manifest,
    generate_l0_report,
    generate_stage37_report,
)

__all__ = [
    "L0Decision",
    "ReadinessDimensionStatus",
    "BenchmarkStabilityStatus",
    "InfrastructureClassification",
    "ObjectiveStatus",
    "ToolContractStatus",
    "ToolContractRecord",
    "CandidateObjective",
    "HardwareAuditReport",
    "ArchitectureStabilityReport",
    "BenchmarkStabilityReport",
    "FailureCategoryAudit",
    "ControlledLoRAExperimentContract",
    "BaselineSnapshot",
    "L0Manifest",
    "get_competition_tool_contracts",
    "verify_tool_contracts",
    "run_hardware_audit",
    "verify_root_prompt_stability",
    "verify_benchmark_stability",
    "audit_failure_taxonomy",
    "get_candidate_objectives",
    "select_objectives",
    "verify_architecture_stability",
    "capture_baseline_snapshot",
    "build_experiment_contract",
    "build_no_adapter_control",
    "determine_l0_decision",
    "build_l0_manifest",
    "generate_l0_report",
    "generate_stage37_report",
]
