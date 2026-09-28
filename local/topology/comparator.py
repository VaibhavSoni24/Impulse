"""Topology comparison and decision logic for Stage 24 experiments.

Implements:
- Markdown comparison table generation across M0–M5.
- Decision framework implementing: "Select the smallest topology that materially improves held-out performance."
- Strict handling of missing evidence (UNRESOLVED selection status without fabrication).
"""

from __future__ import annotations

from typing import Any
from local.topology.matrix import CANONICAL_TOPOLOGY_MATRIX, get_topology_definition
from local.topology.models import SelectionStatus, TopologyAggregateMetrics


def generate_topology_comparison_table(
    metrics_map: dict[str, TopologyAggregateMetrics],
) -> str:
    """Renders a neutral markdown comparison table across all six topologies (M0 to M5)."""
    header = (
        "| Topology | Name | Specialists | Pass Rate | Avg Runtime (s) | Avg Turns | Avg Tool Calls | Recovery Rate | Evidence Status |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    rows: list[str] = []

    for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
        defn = CANONICAL_TOPOLOGY_MATRIX[tid]
        specs = ", ".join(defn.specialists) if defn.specialists else "*(none)*"
        m = metrics_map.get(tid)

        if m is None or m.evidence_status == "UNEXECUTED" or m.pass_rate is None:
            pass_rate_str = "null"
            runtime_str = "null"
            turns_str = "null"
            tools_str = "null"
            recovery_str = "null"
            status_str = "UNEXECUTED"
        else:
            pass_rate_str = f"{m.pass_rate * 100:.1f}%"
            runtime_str = f"{m.avg_runtime_seconds:.1f}" if m.avg_runtime_seconds is not None else "null"
            turns_str = f"{m.avg_turns:.1f}" if m.avg_turns is not None else "null"
            tools_str = f"{m.avg_tool_calls:.1f}" if m.avg_tool_calls is not None else "null"
            recovery_str = f"{m.recovery_success_rate * 100:.1f}%" if m.recovery_success_rate is not None else "N/A"
            status_str = m.evidence_status

        rows.append(
            f"| `{tid}` | `{defn.name}` | {specs} | {pass_rate_str} | {runtime_str} | {turns_str} | {tools_str} | {recovery_str} | `{status_str}` |"
        )

    return header + "\n".join(rows) + "\n"


def evaluate_topology_selection(
    metrics_map: dict[str, TopologyAggregateMetrics],
    has_held_out_evidence: bool = False,
    min_pass_rate_improvement: float = 0.05,
) -> tuple[SelectionStatus, str, str | None]:
    """Evaluates candidate topologies to select the smallest topology that materially improves held-out performance.

    Rules:
    1. If no live benchmark data is available across topologies -> UNRESOLVED.
    2. If validation/held-out confirmation is not verified -> UNRESOLVED.
    3. Smallest topology preference: among topologies with statistically comparable outcomes
       (within min_pass_rate_improvement of the maximum observed pass rate), the candidate with
       the fewest specialist sub-agents is selected.
    4. Never selects M5 automatically without empirical evidence.
    """
    # Check for empty or unexecuted benchmark evidence
    measured_topologies = {
        tid: m
        for tid, m in metrics_map.items()
        if m is not None and m.evidence_status == "MEASURED" and m.pass_rate is not None
    }

    if not measured_topologies:
        return (
            SelectionStatus.UNRESOLVED,
            "No empirical benchmark results available. All topology performance metrics remain unasserted (null). Selection status is UNRESOLVED.",
            None,
        )

    if not has_held_out_evidence:
        return (
            SelectionStatus.UNRESOLVED,
            "Validation data exists, but held-out evaluation evidence is absent. Promotion requires confirmation on held-out split. Selection status remains UNRESOLVED.",
            None,
        )

    # Find the maximum pass rate achieved
    max_pass_rate = max(m.pass_rate for m in measured_topologies.values())  # type: ignore[arg-type]

    # Filter to candidates that are within min_pass_rate_improvement of the best
    contenders = [
        tid
        for tid, m in measured_topologies.items()
        if m.pass_rate is not None and (max_pass_rate - m.pass_rate) <= min_pass_rate_improvement
    ]

    # Sort contenders by:
    # 1. Specialist count (ascending - smallest topology first)
    # 2. Pass rate (descending)
    def contender_key(tid: str) -> tuple[int, float]:
        defn = get_topology_definition(tid)
        pr = measured_topologies[tid].pass_rate or 0.0
        return (defn.specialist_count, -pr)

    contenders.sort(key=contender_key)
    selected_id = contenders[0]
    selected_defn = get_topology_definition(selected_id)
    selected_metrics = measured_topologies[selected_id]

    reason = (
        f"Selected topology '{selected_id}' ({selected_defn.name}) as the smallest topology "
        f"({selected_defn.specialist_count} specialists: {list(selected_defn.specialists)}) achieving a pass rate of "
        f"{selected_metrics.pass_rate * 100:.1f}%, within the {min_pass_rate_improvement * 100:.1f}% tolerance "
        f"of the best observed pass rate ({max_pass_rate * 100:.1f}%)."
    )

    return SelectionStatus.SELECTED, reason, selected_id
