"""Metrics calculation and aggregation for Stage 24 topology experiments.

Calculates:
- pass rate
- average runtime
- average turns
- average tool calls
- specialist call counts and rates
- failure recovery success rate
"""

from __future__ import annotations

from typing import Any
from local.topology.models import TaskRunRecord, TopologyAggregateMetrics


def calculate_topology_metrics(
    records: list[TaskRunRecord],
    topology_id: str = "UNKNOWN",
) -> TopologyAggregateMetrics:
    """Aggregates a list of TaskRunRecord objects into summary metrics.

    If records is empty, returns unexecuted/null metrics without fabricating numbers.
    """
    if not records:
        return TopologyAggregateMetrics(
            topology_id=topology_id,
            evidence_status="UNEXECUTED",
        )

    tid = records[0].topology_id if records else topology_id
    total_tasks = len(records)
    resolved_tasks = sum(1 for r in records if r.success)
    failed_tasks = total_tasks - resolved_tasks
    pass_rate = resolved_tasks / total_tasks

    avg_runtime = sum(r.elapsed_seconds for r in records) / total_tasks
    avg_turns = sum(r.turns for r in records) / total_tasks
    avg_tool_calls = sum(r.tool_calls for r in records) / total_tasks

    total_spec_calls = sum(sum(r.specialist_calls.values()) for r in records)
    avg_spec_calls = total_spec_calls / total_tasks

    recovery_attempts = sum(1 for r in records if r.recovery_triggered)
    recovery_successes = sum(1 for r in records if r.recovery_triggered and r.recovery_success)
    recovery_rate = (recovery_successes / recovery_attempts) if recovery_attempts > 0 else None

    return TopologyAggregateMetrics(
        topology_id=tid,
        total_tasks=total_tasks,
        resolved_tasks=resolved_tasks,
        failed_tasks=failed_tasks,
        pass_rate=pass_rate,
        avg_runtime_seconds=avg_runtime,
        avg_turns=avg_turns,
        avg_tool_calls=avg_tool_calls,
        avg_specialist_calls=avg_spec_calls,
        total_specialist_calls=total_spec_calls,
        recovery_attempt_count=recovery_attempts,
        recovery_success_count=recovery_successes,
        recovery_success_rate=recovery_rate,
        evidence_status="MEASURED",
    )


def summarize_topology_metrics(metrics: TopologyAggregateMetrics) -> dict[str, Any]:
    """Formats metrics as a serializable summary dictionary."""
    return metrics.to_dict()
