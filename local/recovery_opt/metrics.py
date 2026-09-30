"""Recovery Effectiveness and Cost Metrics (Stage 35 Sections 16, 17, 32, 42).

Computes transparent quantitative dimensions without collapsing into an opaque single score:
- Quality / Effectiveness:
  - targeted_recovery_success_rate
  - targeted_failure_reduction
  - recovery_loop_count
  - detection_latency_events / detection_latency_turns
  - average_recovery_attempts
  - mean_recovery_runtime_ms
  - tasks_recovered_after_failure
  - tasks_abandoned_after_failure
  - alternate_path_success_rate
  - first_attempt_recovery_success_rate
- Cost:
  - recovery_tool_calls
  - recovery_turns
  - retry_count
  - recovery_runtime_ms
  - additional_tests_caused
  - additional_retrieval_calls
  - additional_context_growth_bytes
  - repeated_failed_interventions
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.recovery_opt.earliest_detection import analyze_early_detection
from local.recovery_opt.loop_detector import RecoveryLoopDetector
from local.recovery_opt.models import (
    RecoveryCostMetrics,
    RecoveryExecutionEvent,
    RecoveryOutcome,
    RecoveryQualityMetrics,
    RecoveryTaskPairOutcome,
)


def compute_recovery_cost_metrics(
    events: List[RecoveryExecutionEvent],
) -> RecoveryCostMetrics:
    """Aggregates resource and cost metrics from execution events."""
    if not events:
        return RecoveryCostMetrics()

    total_tool_calls = sum(e.tool_calls_added for e in events)
    turns_used = len(set(e.turn for e in events if e.turn > 0))
    retries = sum(1 for e in events if e.attempt_number > 1)
    runtime_ms = sum(e.duration_ms for e in events)

    extra_tests = 0
    extra_retrievals = 0
    extra_context = 0
    repeated_failed = 0

    for e in events:
        act = (e.action or "").upper()
        if "TEST" in act or "VALIDAT" in act:
            extra_tests += 1
        elif "SEARCH" in act or "RETRIEV" in act or "GRAPH" in act or "TREE" in act:
            extra_retrievals += 1

        extra_context += int(e.metadata.get("output_bytes", 0))
        if e.recovery_outcome == RecoveryOutcome.NOT_RECOVERED.value:
            repeated_failed += 1

    return RecoveryCostMetrics(
        recovery_tool_calls=total_tool_calls,
        recovery_turns=turns_used,
        retry_count=retries,
        recovery_runtime_ms=runtime_ms,
        additional_tests_caused=extra_tests,
        additional_retrieval_calls=extra_retrievals,
        additional_context_growth_bytes=extra_context,
        repeated_failed_interventions=repeated_failed,
    )


def compute_recovery_quality_metrics(
    events: List[RecoveryExecutionEvent],
    target_failure_mode: str = "",
    paired_outcomes: Optional[List[RecoveryTaskPairOutcome]] = None,
) -> RecoveryQualityMetrics:
    """Computes recovery effectiveness, success, and latency metrics."""
    if not events:
        return RecoveryQualityMetrics()

    events_by_task: dict[str, list[RecoveryExecutionEvent]] = {}
    for e in events:
        events_by_task.setdefault(e.task_id, []).append(e)

    loop_detector = RecoveryLoopDetector()
    total_loops = 0
    total_lat_events: list[int] = []
    total_lat_turns: list[int] = []
    total_attempts: list[int] = []
    recovered_tasks = 0
    abandoned_tasks = 0
    alt_path_attempts = 0
    alt_path_successes = 0
    first_attempt_successes = 0

    for tid, task_evs in events_by_task.items():
        # Loop detection
        l_res = loop_detector.analyze_events(task_evs)
        if l_res.loop_detected:
            total_loops += 1

        # Early detection analysis
        ed_rep = analyze_early_detection(task_evs, task_id=tid)
        if ed_rep.detection_latency_events is not None:
            total_lat_events.append(ed_rep.detection_latency_events)
        if ed_rep.detection_latency_turns is not None:
            total_lat_turns.append(ed_rep.detection_latency_turns)

        # Attempts
        max_att = max((e.attempt_number for e in task_evs), default=1)
        total_attempts.append(max_att)

        # Task outcome
        has_recovered = any(
            e.recovery_outcome in [
                RecoveryOutcome.RECOVERED.value,
                RecoveryOutcome.RECOVERED_AFTER_RETRY.value,
                RecoveryOutcome.RECOVERED_AFTER_ALTERNATE_PATH.value,
            ]
            for e in task_evs
        )
        if has_recovered:
            recovered_tasks += 1
            first_att_ev = next((e for e in task_evs if e.attempt_number == 1), None)
            if first_att_ev and first_att_ev.recovery_outcome in [
                RecoveryOutcome.RECOVERED.value,
                RecoveryOutcome.RECOVERED_AFTER_RETRY.value,
            ]:
                first_attempt_successes += 1
        else:
            abandoned_tasks += 1

        # Alternate path tracking
        for e in task_evs:
            is_alt = (
                "ALTERNATE" in (e.action or "").upper()
                or "ALTERNATE" in (e.trigger or "").upper()
                or e.recovery_outcome == RecoveryOutcome.RECOVERED_AFTER_ALTERNATE_PATH.value
            )
            if is_alt:
                alt_path_attempts += 1
                if e.recovery_outcome in [
                    RecoveryOutcome.RECOVERED.value,
                    RecoveryOutcome.RECOVERED_AFTER_ALTERNATE_PATH.value,
                ]:
                    alt_path_successes += 1

    total_tasks = len(events_by_task)
    success_rate = (recovered_tasks / total_tasks) if total_tasks > 0 else 0.0
    mean_lat_events = (sum(total_lat_events) / len(total_lat_events)) if total_lat_events else 0.0
    mean_lat_turns = (sum(total_lat_turns) / len(total_lat_turns)) if total_lat_turns else 0.0
    avg_attempts = (sum(total_attempts) / len(total_attempts)) if total_attempts else 0.0
    mean_runtime_ms = (sum(e.duration_ms for e in events) / total_tasks) if total_tasks > 0 else 0.0
    alt_rate = (alt_path_successes / alt_path_attempts) if alt_path_attempts > 0 else 0.0
    first_att_rate = (first_attempt_successes / total_tasks) if total_tasks > 0 else 0.0

    target_red = 0
    if paired_outcomes:
        target_red = sum(1 for p in paired_outcomes if p.transition == "FAIL_TO_RECOVERED")

    return RecoveryQualityMetrics(
        targeted_recovery_success_rate=success_rate,
        targeted_failure_reduction=target_red,
        recovery_loop_count=total_loops,
        detection_latency_events=mean_lat_events,
        detection_latency_turns=mean_lat_turns,
        average_recovery_attempts=avg_attempts,
        mean_recovery_runtime_ms=mean_runtime_ms,
        tasks_recovered_after_failure=recovered_tasks,
        tasks_abandoned_after_failure=abandoned_tasks,
        alternate_path_success_rate=alt_rate,
        first_attempt_recovery_success_rate=first_att_rate,
    )
