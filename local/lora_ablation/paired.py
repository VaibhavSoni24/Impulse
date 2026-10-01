"""Task-Paired Analyzer and Collateral Regression Evaluator for Stage 40 (Section 11, 12).

Performs rigorous 1-to-1 task pairing between Condition A and Condition B:
- 2x2 outcome transition matrix (A_PASS_B_PASS, A_PASS_B_FAIL, A_FAIL_B_PASS, A_FAIL_B_FAIL)
- Target-specific failure transitions (TARGET_FAILURE_RESOLVED, TARGET_FAILURE_REMAINS, NEW_TARGET_FAILURE)
- Collateral regression detection (verifies that adapter does not break previously-passing tasks)
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from local.lora_ablation.models import (
    CollateralStatus,
    PairedTaskComparison,
    TargetFailureTransition,
    TaskEvaluationRecord,
    TaskPairTransition,
)


class TaskPairedAnalyzer:
    """Analyzes causal behavioral differences across paired tasks under Condition A vs B."""

    @classmethod
    def classify_task_transition(
        cls, a_rec: TaskEvaluationRecord, b_rec: TaskEvaluationRecord
    ) -> TaskPairTransition:
        """Determines the 2x2 pass/fail transition for an individual task."""
        if a_rec.success and b_rec.success:
            return TaskPairTransition.A_PASS_B_PASS
        elif a_rec.success and not b_rec.success:
            return TaskPairTransition.A_PASS_B_FAIL
        elif not a_rec.success and b_rec.success:
            return TaskPairTransition.A_FAIL_B_PASS
        else:
            return TaskPairTransition.A_FAIL_B_FAIL

    @classmethod
    def classify_target_transition(
        cls, a_rec: TaskEvaluationRecord, b_rec: TaskEvaluationRecord
    ) -> TargetFailureTransition:
        """Determines whether the target behavior (repeated failing commands) changed."""
        a_had_target = a_rec.repeated_failing_command_count > 0 or a_rec.failure_class == "COMMAND"
        b_had_target = b_rec.repeated_failing_command_count > 0 or b_rec.failure_class == "COMMAND"

        if a_had_target and not b_had_target:
            return TargetFailureTransition.TARGET_FAILURE_RESOLVED
        elif a_had_target and b_had_target:
            return TargetFailureTransition.TARGET_FAILURE_REMAINS
        elif not a_had_target and b_had_target:
            return TargetFailureTransition.NEW_TARGET_FAILURE
        elif not a_rec.success and not b_rec.success and a_rec.failure_class != b_rec.failure_class:
            return TargetFailureTransition.OTHER_FAILURE_CHANGED
        else:
            return TargetFailureTransition.NO_TARGET_FAILURE

    @classmethod
    def compare_task_pair(
        cls, a_rec: TaskEvaluationRecord, b_rec: TaskEvaluationRecord
    ) -> PairedTaskComparison:
        """Builds a comprehensive comparison record for a single paired task."""
        task_trans = cls.classify_task_transition(a_rec, b_rec)
        target_trans = cls.classify_target_transition(a_rec, b_rec)

        # Assess collateral status for this task
        if task_trans == TaskPairTransition.A_PASS_B_FAIL:
            collateral = CollateralStatus.COLLATERAL_REGRESSION
        elif task_trans == TaskPairTransition.A_FAIL_B_PASS or target_trans == TargetFailureTransition.TARGET_FAILURE_RESOLVED:
            collateral = CollateralStatus.TARGET_GAIN
        else:
            collateral = CollateralStatus.UNCHANGED

        return PairedTaskComparison(
            task_id=a_rec.task_id,
            task_transition=task_trans,
            target_transition=target_trans,
            collateral_status=collateral,
            a_record=a_rec,
            b_record=b_rec,
            repeated_failing_delta=b_rec.repeated_failing_command_count - a_rec.repeated_failing_command_count,
            tool_invocation_error_delta=b_rec.tool_invocation_error_count - a_rec.tool_invocation_error_count,
            runtime_delta_ms=b_rec.runtime_ms - a_rec.runtime_ms,
            tool_call_delta=b_rec.tool_calls - a_rec.tool_calls,
        )

    @classmethod
    def analyze_task_sets(
        cls,
        a_records: List[TaskEvaluationRecord],
        b_records: List[TaskEvaluationRecord],
    ) -> Tuple[List[PairedTaskComparison], CollateralStatus, Dict[str, int]]:
        """Pairs tasks by task_id and evaluates overall collateral status and transitions.

        Returns:
            (paired_comparisons, overall_collateral_status, transition_counts)
        """
        a_by_id = {r.task_id: r for r in a_records}
        b_by_id = {r.task_id: r for r in b_records}

        common_ids = sorted(set(a_by_id.keys()) & set(b_by_id.keys()))
        paired: List[PairedTaskComparison] = []

        transition_counts: Dict[str, int] = {
            TaskPairTransition.A_PASS_B_PASS.value: 0,
            TaskPairTransition.A_PASS_B_FAIL.value: 0,
            TaskPairTransition.A_FAIL_B_PASS.value: 0,
            TaskPairTransition.A_FAIL_B_FAIL.value: 0,
            TargetFailureTransition.TARGET_FAILURE_RESOLVED.value: 0,
            TargetFailureTransition.TARGET_FAILURE_REMAINS.value: 0,
            TargetFailureTransition.NEW_TARGET_FAILURE.value: 0,
        }

        for tid in common_ids:
            p = cls.compare_task_pair(a_by_id[tid], b_by_id[tid])
            paired.append(p)
            transition_counts[p.task_transition.value] += 1
            if p.target_transition.value in transition_counts:
                transition_counts[p.target_transition.value] += 1

        # Determine overall collateral status
        regressions = transition_counts[TaskPairTransition.A_PASS_B_FAIL.value]
        gains = transition_counts[TaskPairTransition.A_FAIL_B_PASS.value]
        resolved = transition_counts[TargetFailureTransition.TARGET_FAILURE_RESOLVED.value]

        if regressions > 0:
            overall_status = CollateralStatus.COLLATERAL_REGRESSION
        elif gains > 0 or resolved > 0:
            overall_status = CollateralStatus.TARGET_GAIN
        else:
            overall_status = CollateralStatus.UNCHANGED

        return (paired, overall_status, transition_counts)
