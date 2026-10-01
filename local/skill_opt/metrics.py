"""Skill Metrics and Pareto Analysis Engine (Stage 36 Sections 19, 20, 22).

Computes transparent quantitative dimensions without collapsing into an opaque single score:
- Context Cost Metrics:
  - character, line, word, estimated token counts and deltas
- Behavioral Signals:
  - task success rate
  - target failure count and rate
  - command redundancy count
  - repeated reconnaissance count
  - test discovery repetitions
  - unnecessary tree scans
  - redundant file reads
  - average tool calls, turns, runtime ms
- Quality / Cost Pareto Evaluation:
  - Detects if candidate strictly dominates parent (better or equal quality with lower context cost)
  - Detects regressions in behavior or unacceptable bloat
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.skill_opt.diff import compute_metrics
from local.skill_opt.models import SkillBehaviorMetrics, SkillContextCostMetrics, SkillScopeType


def compute_skill_context_metrics(
    skill_text: str,
    parent_text: Optional[str] = None,
) -> SkillContextCostMetrics:
    """Computes exact size and token metrics and deltas relative to parent skill."""
    cand_m = compute_metrics(skill_text)
    if parent_text is None:
        return cand_m

    parent_m = compute_metrics(parent_text)
    return SkillContextCostMetrics(
        char_count=cand_m.char_count,
        line_count=cand_m.line_count,
        word_count=cand_m.word_count,
        estimated_tokens=cand_m.estimated_tokens,
        char_delta=cand_m.char_count - parent_m.char_count,
        line_delta=cand_m.line_count - parent_m.line_count,
        word_delta=cand_m.word_count - parent_m.word_count,
        token_delta=cand_m.estimated_tokens - parent_m.estimated_tokens,
    )


def compute_skill_behavior_metrics(
    events: List[Dict[str, Any]],
    skill_scope: str = SkillScopeType.GENERAL.value,
) -> SkillBehaviorMetrics:
    """Aggregates behavioral telemetry events from evaluation traces."""
    if not events:
        return SkillBehaviorMetrics()

    total_tasks = len(set(e.get("task_id", "") for e in events if e.get("task_id")))
    if total_tasks == 0:
        total_tasks = 1

    success_count = sum(1 for e in events if e.get("success") and e.get("is_task_final", True))
    target_failure_count = sum(1 for e in events if e.get("target_failure_detected"))
    cmd_redundancy = sum(1 for e in events if e.get("is_redundant_command"))
    repeated_reconn = sum(1 for e in events if e.get("repeated_reconnaissance"))
    test_disc_reps = sum(1 for e in events if e.get("repeated_test_discovery"))
    irrelevant_tests = sum(1 for e in events if e.get("irrelevant_test_executed"))
    tree_scans = sum(1 for e in events if e.get("unnecessary_tree_scan"))
    redundant_reads = sum(1 for e in events if e.get("redundant_file_read"))

    tool_calls = sum(e.get("tool_calls_count", 0) for e in events)
    turns = sum(e.get("turns_count", 0) for e in events)
    runtime = sum(e.get("runtime_ms", 0.0) for e in events)
    files_read = sum(e.get("files_read_count", 0) for e in events)
    files_changed = sum(e.get("files_changed_count", 0) for e in events)
    retrievals = sum(1 for e in events if e.get("is_retrieval_action"))
    recoveries = sum(1 for e in events if e.get("is_recovery_action"))

    pm_detected = any(e.get("package_manager_detected") for e in events) if events else None
    fw_detected = any(e.get("framework_detected") for e in events) if events else None
    tf_detected = any(e.get("test_framework_detected") for e in events) if events else None
    ep_detected = any(e.get("entry_points_discovered") for e in events) if events else None

    # Test selection quality ratio
    total_tests_run = sum(e.get("tests_executed_count", 0) for e in events)
    relevant_tests_run = total_tests_run - irrelevant_tests
    test_qual = (relevant_tests_run / total_tests_run) if total_tests_run > 0 else 1.0

    return SkillBehaviorMetrics(
        task_success_rate=success_count / total_tasks,
        target_failure_count=target_failure_count,
        target_failure_rate=target_failure_count / total_tasks,
        command_redundancy_count=cmd_redundancy,
        repeated_reconnaissance_count=repeated_reconn,
        test_discovery_repetitions=test_disc_reps,
        irrelevant_test_executions=irrelevant_tests,
        unnecessary_tree_scans=tree_scans,
        redundant_file_reads=redundant_reads,
        package_manager_detected=pm_detected,
        framework_detected=fw_detected,
        test_framework_detected=tf_detected,
        entry_points_discovered=ep_detected,
        avg_tool_calls=tool_calls / total_tasks,
        avg_turns=turns / total_tasks,
        avg_runtime_ms=runtime / total_tasks,
        files_read_count=files_read,
        files_changed_count=files_changed,
        retrieval_interactions=retrievals,
        recovery_interactions=recoveries,
        test_selection_quality=test_qual,
    )


def compare_skill_metrics(
    parent_behavior: SkillBehaviorMetrics,
    candidate_behavior: SkillBehaviorMetrics,
    cost_metrics: SkillContextCostMetrics,
) -> Dict[str, Any]:
    """Compares behavioral shifts and cost deltas against Pareto criteria."""
    success_delta = candidate_behavior.task_success_rate - parent_behavior.task_success_rate
    target_fail_delta = candidate_behavior.target_failure_count - parent_behavior.target_failure_count
    redundancy_delta = candidate_behavior.command_redundancy_count - parent_behavior.command_redundancy_count
    recon_delta = candidate_behavior.repeated_reconnaissance_count - parent_behavior.repeated_reconnaissance_count
    test_disc_delta = candidate_behavior.test_discovery_repetitions - parent_behavior.test_discovery_repetitions
    token_delta = cost_metrics.token_delta

    # Quality regressed if success dropped or target failures increased or severe collateral redundancy increase
    quality_regressed = (
        success_delta < 0
        or target_fail_delta > 0
        or (redundancy_delta > 0 and success_delta <= 0)
    )

    # Quality improved if not regressed and target failures reduced, or success increased, or redundancy reduced with non-negative success
    quality_improved = (not quality_regressed) and (
        success_delta > 0
        or target_fail_delta < 0
        or (redundancy_delta < 0 and success_delta >= 0)
        or (recon_delta < 0 and success_delta >= 0)
        or (test_disc_delta < 0 and success_delta >= 0)
    )

    cost_reduced = token_delta < 0
    cost_increased = token_delta > 0

    if quality_regressed:
        pareto_status = "REGRESSION"
    elif quality_improved and cost_reduced:
        pareto_status = "STRICTLY_DOMINATES"  # Higher quality, lower context cost
    elif quality_improved and not cost_increased:
        pareto_status = "PARETO_IMPROVEMENT"
    elif quality_improved and cost_increased:
        pareto_status = "TRADE_OFF_EXPENSIVE_IMPROVEMENT"
    elif not quality_improved and not quality_regressed and cost_reduced:
        pareto_status = "LEANER_EQUIVALENT"  # Same performance with less context bloat
    elif not quality_improved and cost_increased:
        pareto_status = "STRICTLY_DOMINATED_BLOAT"  # No benefit, more tokens
    else:
        pareto_status = "NEUTRAL"

    return {
        "success_delta": success_delta,
        "target_failure_delta": target_fail_delta,
        "redundancy_delta": redundancy_delta,
        "reconnaissance_delta": recon_delta,
        "test_discovery_delta": test_disc_delta,
        "token_delta": token_delta,
        "quality_improved": quality_improved,
        "quality_regressed": quality_regressed,
        "pareto_status": pareto_status,
    }
