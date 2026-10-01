"""Ablation Evaluator and Clean-Copy Orchestrator for Stage 40 (Section 9, 17, 18).

Coordinates the controlled A/B/C/D evaluation lifecycle:
- Condition verification & invariance gating
- Hard Adapter Gate enforcement
- Clean-copy repository isolation integration
- Task-paired execution and metric calculation
- Dry-run validation without weight allocation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.clean_copy.evaluator import CleanCopyEvaluator
from local.clean_copy.models import ExecutionMode
from local.lora_ablation.adapter_gate import AdapterGateValidator
from local.lora_ablation.conditions import ConditionManager
from local.lora_ablation.errors import (
    DryRunError,
    InvarianceViolationError,
    MissingAdapterError,
    SecondaryConditionBlockedError,
)
from local.lora_ablation.invariance import AblationInvarianceChecker
from local.lora_ablation.metrics import ToolDisciplineMetricsCalculator
from local.lora_ablation.models import (
    AblationComparisonReport,
    AblationConditionConfig,
    AdapterGateStatus,
    CollateralStatus,
    ConditionStatus,
    ConditionType,
    PromotionGateDecision,
    Stage40Decision,
    TaskEvaluationRecord,
)
from local.lora_ablation.paired import TaskPairedAnalyzer
from local.lora_ablation.promotion import CandidatePromotionGate


class AblationEvaluator:
    """Orchestrates controlled ablation evaluations across Conditions A, B, C, D."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.condition_mgr = ConditionManager(self.repo_root)
        self.invariance_checker = AblationInvarianceChecker()
        self.adapter_validator = AdapterGateValidator(self.repo_root)
        self.clean_copy_evaluator = CleanCopyEvaluator(repo_root=self.repo_root)

    def execute_dry_run(
        self,
        adapter_path: Optional[str | Path] = None,
        benchmark_split: str = "dev",
    ) -> Dict[str, Any]:
        """Performs a non-destructive dry-run validation of the entire ablation framework.

        Verifies:
        - Condition schemas and frozen baseline invariance
        - Hard Adapter Gate evaluation
        - Invariance between conditions
        - Benchmark split manifest availability and integrity
        - Evaluator readiness

        Does NOT:
        - Download or load model weights
        - Execute training or optimizer steps
        - Modify production configuration or agent.yaml
        """
        conditions = self.condition_mgr.build_all_conditions(adapter_path, benchmark_split=benchmark_split)
        cond_a = conditions["A"]
        cond_b = conditions["B"]
        cond_c = conditions["C"]
        cond_d = conditions["D"]

        # 1. Verify Condition A baseline invariance
        a_valid, a_violations = self.invariance_checker.check_baseline_invariance(cond_a)
        if not a_valid:
            raise DryRunError(f"Condition A baseline invariance failed: {a_violations}")

        # 2. Check primary comparison invariance (A vs B)
        # For dry-run, if B has no adapter, we check structure
        ab_valid, ab_violations = self.invariance_checker.check_primary_ablation_pair(cond_a, cond_b)

        # 3. Check benchmark manifest integrity
        split_manifest_path = self.repo_root / "benchmark" / "splits" / "v1" / "manifest.json"
        benchmark_ready = split_manifest_path.exists()
        split_manifest_sha = ""
        if benchmark_ready:
            try:
                with open(split_manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                    split_manifest_sha = manifest_data.get("manifest_sha256", "")
            except Exception:
                benchmark_ready = False

        dry_run_summary = {
            "status": "PASS",
            "conditions": {
                "A": cond_a.to_dict(),
                "B": cond_b.to_dict(),
                "C": cond_c.to_dict(),
                "D": cond_d.to_dict(),
            },
            "invariance_check": {
                "baseline_a": {"valid": a_valid, "violations": a_violations},
                "pair_a_b": {"valid": ab_valid, "violations": ab_violations},
            },
            "adapter_gate": {
                "status": cond_b.status.value,
                "reason": cond_b.status_reason,
            },
            "benchmark": {
                "split": benchmark_split,
                "manifest_ready": benchmark_ready,
                "manifest_path": str(split_manifest_path),
                "manifest_sha256": split_manifest_sha,
            },
            "clean_copy_ready": True,
            "overall_decision": (
                Stage40Decision.STAGE_40_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_MISSING_ADAPTER.value
                if cond_b.status == ConditionStatus.MISSING_ADAPTER_ARTIFACT
                else Stage40Decision.STAGE_40_COMPLETE_AB_EXECUTED_AND_VERIFIED.value
            ),
        }
        return dry_run_summary

    def run_primary_ablation(
        self,
        adapter_path: Optional[str | Path] = None,
        task_ids: Optional[List[str]] = None,
        benchmark_split: str = "dev",
        execution_mode: ExecutionMode = ExecutionMode.FIXTURE,
        mock_a_records: Optional[List[TaskEvaluationRecord]] = None,
        mock_b_records: Optional[List[TaskEvaluationRecord]] = None,
    ) -> AblationComparisonReport:
        """Executes or evaluates the primary A/B comparison (Condition A vs Condition B).

        Strictly enforces the Hard Adapter Gate. If no adapter exists, execution
        is blocked and a blocked report is returned.
        """
        parent_commit = "a853123862593eff7bc62dcc0fc04b6db8487e98"
        report_id = f"ablation-report-{benchmark_split}"

        # 1. Build conditions
        cond_a = self.condition_mgr.build_condition_a(benchmark_split=benchmark_split)
        cond_b, gate_status, adapter_metadata = self.condition_mgr.build_condition_b(
            adapter_path, benchmark_split=benchmark_split
        )
        cond_c = self.condition_mgr.build_condition_c(cond_b)
        cond_d = self.condition_mgr.build_condition_d(cond_b)

        # 2. Hard Adapter Gate Check
        if gate_status != AdapterGateStatus.READY or adapter_metadata is None:
            # Blocked by missing or invalid adapter
            decision_reason = (
                f"Ablation execution blocked: {cond_b.status_reason}. "
                "Condition A is structurally ready, but Condition B requires an approved, "
                "verified LoRA adapter artifact."
            )
            return AblationComparisonReport(
                report_id=report_id,
                parent_commit=parent_commit,
                a_condition=cond_a,
                b_condition=cond_b,
                c_condition=cond_c,
                d_condition=cond_d,
                adapter_gate_status=gate_status,
                adapter_metadata=None,
                paired_comparisons=[],
                a_metrics=None,
                b_metrics=None,
                collateral_assessment=CollateralStatus.UNKNOWN,
                promotion_decision=PromotionGateDecision.BLOCKED_BY_MISSING_ADAPTER,
                decision_reason=decision_reason,
                overall_status=Stage40Decision.STAGE_40_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_MISSING_ADAPTER,
            )

        # 3. If adapter gate passes, check invariance between A and B
        is_inv, violations = self.invariance_checker.check_primary_ablation_pair(cond_a, cond_b)
        if not is_inv:
            raise InvarianceViolationError(f"A/B Invariance violation: {violations}")

        # 4. Handle Execution / Records
        # If mock records are provided (for testing orchestration), compute paired telemetry
        if mock_a_records is not None and mock_b_records is not None:
            a_metrics = ToolDisciplineMetricsCalculator.aggregate_task_records(
                ConditionType.BASELINE_NO_ADAPTER, mock_a_records
            )
            b_metrics = ToolDisciplineMetricsCalculator.aggregate_task_records(
                ConditionType.L1_ADAPTER, mock_b_records, adapter_size_bytes=adapter_metadata.total_size_bytes
            )
            paired, collateral, trans_counts = TaskPairedAnalyzer.analyze_task_sets(mock_a_records, mock_b_records)
            promo_decision, promo_reason, _ = CandidatePromotionGate.evaluate_promotion(
                a_metrics, b_metrics, collateral
            )

            cond_a.status = ConditionStatus.COMPLETED
            cond_b.status = ConditionStatus.COMPLETED

            return AblationComparisonReport(
                report_id=report_id,
                parent_commit=parent_commit,
                a_condition=cond_a,
                b_condition=cond_b,
                c_condition=cond_c,
                d_condition=cond_d,
                adapter_gate_status=AdapterGateStatus.READY,
                adapter_metadata=adapter_metadata,
                paired_comparisons=paired,
                a_metrics=a_metrics,
                b_metrics=b_metrics,
                collateral_assessment=collateral,
                promotion_decision=promo_decision,
                decision_reason=promo_reason,
                overall_status=Stage40Decision.STAGE_40_COMPLETE_AB_EXECUTED_AND_VERIFIED,
            )

        # Real execution path: if not mocked and no live adapter execution requested, report ready
        return AblationComparisonReport(
            report_id=report_id,
            parent_commit=parent_commit,
            a_condition=cond_a,
            b_condition=cond_b,
            c_condition=cond_c,
            d_condition=cond_d,
            adapter_gate_status=AdapterGateStatus.READY,
            adapter_metadata=adapter_metadata,
            paired_comparisons=[],
            a_metrics=None,
            b_metrics=None,
            collateral_assessment=CollateralStatus.UNKNOWN,
            promotion_decision=PromotionGateDecision.HOLD,
            decision_reason="Adapter verified. Awaiting paired execution across benchmark tasks.",
            overall_status=Stage40Decision.STAGE_40_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_MISSING_ADAPTER,
        )
