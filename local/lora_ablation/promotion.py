"""Candidate Promotion Gate for Stage 40 LoRA Ablation (Section 14, 23).

Enforces the project promotion policy:
- Validation improvement on primary objective (OBJ-TOOL-DISCIPLINE)
- No unacceptable held-out regression
- No collateral regressions (A_PASS_B_FAIL == 0)
- Acceptable runtime budget
- Zero automatic promotion: outputs formal decision without ever touching production agent.yaml.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from local.lora_ablation.models import (
    AblationAggregateMetrics,
    CollateralStatus,
    PromotionGateDecision,
)


class CandidatePromotionGate:
    """Evaluates whether an L1 adapter candidate qualifies for promotion consideration."""

    @staticmethod
    def evaluate_promotion(
        a_metrics: Optional[AblationAggregateMetrics],
        b_metrics: Optional[AblationAggregateMetrics],
        collateral_status: CollateralStatus,
        held_out_regressions: int = 0,
        max_allowed_runtime_ms: float = 300000.0,
    ) -> Tuple[PromotionGateDecision, str, List[str]]:
        """Evaluates promotion criteria for candidate L1 against baseline control A.

        Returns:
            (decision, primary_rationale, list_of_reasons)
        """
        reasons: List[str] = []

        if a_metrics is None or b_metrics is None:
            return (
                PromotionGateDecision.BLOCKED_BY_MISSING_ADAPTER,
                "Promotion evaluation blocked: missing metrics for Condition A or B.",
                ["Missing evaluation telemetry."],
            )

        # 1. Check Collateral Regression (tasks that passed in A must not fail in B)
        if collateral_status == CollateralStatus.COLLATERAL_REGRESSION:
            reasons.append("Collateral regression detected: adapter caused previously-passing tasks to fail.")

        # 2. Check Held-Out Regression
        if held_out_regressions > 0:
            reasons.append(f"Held-out benchmark regression detected ({held_out_regressions} regressed tasks).")

        # 3. Check Primary Objective Improvement (repeated failing commands)
        target_improved = b_metrics.total_repeated_failing_commands < a_metrics.total_repeated_failing_commands
        overall_pass_improved = b_metrics.pass_rate >= a_metrics.pass_rate

        if not target_improved and not (b_metrics.pass_rate > a_metrics.pass_rate):
            reasons.append(
                f"No measurable improvement on OBJ-TOOL-DISCIPLINE: "
                f"repeated failing commands went from {a_metrics.total_repeated_failing_commands} to {b_metrics.total_repeated_failing_commands}."
            )

        # 4. Check Runtime Budget
        if b_metrics.avg_runtime_ms > max_allowed_runtime_ms:
            reasons.append(
                f"Average runtime {b_metrics.avg_runtime_ms:.1f}ms exceeds maximum allowed {max_allowed_runtime_ms:.1f}ms."
            )

        # Decision synthesis
        if not reasons and (target_improved or b_metrics.pass_rate > a_metrics.pass_rate):
            return (
                PromotionGateDecision.PROMOTE,
                "Candidate qualifies for promotion: verified target improvement with zero collateral or held-out regressions.",
                ["Primary metric improved.", "Zero collateral regressions.", "Runtime within budget."],
            )
        elif collateral_status == CollateralStatus.COLLATERAL_REGRESSION or held_out_regressions > 0:
            return (
                PromotionGateDecision.REJECT,
                "Candidate rejected due to regressions.",
                reasons,
            )
        else:
            return (
                PromotionGateDecision.HOLD,
                "Candidate on hold: insufficient evidence of target behavioral gain.",
                reasons,
            )
