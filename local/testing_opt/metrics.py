"""Testing Cost and Evidence Yield Metrics Engine (Stage 34 Sections 13, 14, 29, 30).

Provides:
- Quantitative cost calculation (command counts, test cases, latencies, output bytes, shares)
- Quantitative validation quality metrics (regressions detected, false-confidence cases, early detection)
- Non-opaque Quality-vs-Cost Pareto frontier evaluation
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from local.fdd.models import FailureRecord
from local.testing_opt.models import (
    TestCostMetrics,
    TestEvidenceMetrics,
    TestExecutionEvent,
    TestLevel,
    TestTaskPairOutcome,
)


def compute_test_cost_metrics(
    events: List[TestExecutionEvent],
    total_agent_runtime_ms: Optional[float] = None,
    total_agent_tool_calls: Optional[int] = None,
) -> TestCostMetrics:
    """Computes comprehensive execution cost metrics from test execution telemetry."""
    total_commands = len(events)
    targeted_cmds = sum(1 for e in events if e.test_level == TestLevel.TARGETED.value)
    adjacent_cmds = sum(1 for e in events if e.test_level == TestLevel.ADJACENT.value)
    subsystem_cmds = sum(1 for e in events if e.test_level == TestLevel.SUBSYSTEM.value)
    full_cmds = sum(1 for e in events if e.test_level == TestLevel.FULL.value)

    total_tests_executed = sum(e.tests_executed for e in events)
    total_runtime = sum(e.duration_ms for e in events)
    total_output_bytes = sum(e.output_size_bytes for e in events)

    durations = [e.duration_ms for e in events if e.duration_ms > 0]
    mean_dur: Optional[float] = None
    median_dur: Optional[float] = None
    p95_dur: Optional[float] = None

    if durations:
        durations.sort()
        mean_dur = sum(durations) / len(durations)
        mid = len(durations) // 2
        median_dur = (
            durations[mid]
            if len(durations) % 2 != 0
            else (durations[mid - 1] + durations[mid]) / 2.0
        )
        p95_idx = int(math.ceil(0.95 * len(durations))) - 1
        p95_dur = durations[min(max(0, p95_idx), len(durations) - 1)]

    repeated_cmds = sum(1 for e in events if e.metadata.get("is_duplicate_command", False))
    dup_cases = sum(e.metadata.get("duplicate_cases_count", 0) for e in events)

    tool_call_share: Optional[float] = None
    if total_agent_tool_calls is not None and total_agent_tool_calls > 0:
        tool_call_share = round(total_commands / total_agent_tool_calls, 4)

    return TestCostMetrics(
        total_test_commands=total_commands,
        targeted_commands=targeted_cmds,
        adjacent_commands=adjacent_cmds,
        subsystem_commands=subsystem_cmds,
        full_suite_commands=full_cmds,
        total_tests_executed=total_tests_executed,
        total_test_runtime_ms=round(total_runtime, 2),
        mean_test_duration_ms=round(mean_dur, 2) if mean_dur is not None else None,
        median_test_duration_ms=round(median_dur, 2) if median_dur is not None else None,
        p95_test_duration_ms=round(p95_dur, 2) if p95_dur is not None else None,
        total_output_bytes=total_output_bytes,
        repeated_command_count=repeated_cmds,
        duplicate_test_case_count=dup_cases,
        total_agent_runtime_ms=total_agent_runtime_ms,
        testing_tool_call_share=tool_call_share,
    )


def compute_test_evidence_metrics(
    candidate_records: Optional[List[FailureRecord]] = None,
    target_failure_mode: str = "UNKNOWN",
    events: Optional[List[TestExecutionEvent]] = None,
    paired_outcomes: Optional[List[TestTaskPairOutcome]] = None,
    clean_copy_success: bool = True,
) -> TestEvidenceMetrics:
    """Computes validation quality, failure detection yield, and false-confidence reduction."""
    recs = candidate_records or []
    total_tasks = len(recs)

    pass_count = sum(1 for r in recs if r.success is True)
    fail_count = sum(1 for r in recs if r.success is False)

    targeted_count = sum(
        1 for r in recs
        if not r.success and (
            r.failure_category == target_failure_mode
            or getattr(r, "error_type", None) == target_failure_mode
        )
    )

    pass_rate = round(pass_count / total_tasks, 4) if total_tasks > 0 else 0.0
    failure_rate = round(fail_count / total_tasks, 4) if total_tasks > 0 else 0.0
    targeted_rate = round(targeted_count / total_tasks, 4) if total_tasks > 0 else 0.0

    ev_list = events or []

    # Level-specific failures discovered
    adj_fails = sum(
        e.failures_detected for e in ev_list
        if e.test_level == TestLevel.ADJACENT.value and e.failures_detected > 0
    )
    sub_fails = sum(
        e.failures_detected for e in ev_list
        if e.test_level == TestLevel.SUBSYSTEM.value and e.failures_detected > 0
    )
    full_fails = sum(
        e.failures_detected for e in ev_list
        if e.test_level == TestLevel.FULL.value and e.failures_detected > 0
    )

    # Regressions detected
    regressions_detected = adj_fails + sub_fails + full_fails

    # Targeted behavior confirmed: targeted tests that passed
    targeted_confirmed = sum(
        1 for e in ev_list
        if e.test_level == TestLevel.TARGETED.value and e.result in ("PASS", "PASSED")
    )

    # Incomplete fixes detected: targeted tests that failed
    incomplete_fixes = sum(
        1 for e in ev_list
        if e.test_level == TestLevel.TARGETED.value and e.result in ("FAIL", "FAILED", "ERROR")
    )

    # False confidence cases:
    # An earlier level (e.g. TARGETED) passed, but a broader level (ADJACENT, SUBSYSTEM, FULL) caught a failure
    false_confidence = 0
    task_events_map: Dict[str, List[TestExecutionEvent]] = {}
    for e in ev_list:
        task_events_map.setdefault(e.task_id, []).append(e)

    for tid, t_events in task_events_map.items():
        targeted_passes = any(e.test_level == TestLevel.TARGETED.value and e.result in ("PASS", "PASSED") for e in t_events)
        broader_fails = any(e.test_level != TestLevel.TARGETED.value and e.result in ("FAIL", "FAILED", "ERROR") for e in t_events)
        if targeted_passes and broader_fails:
            false_confidence += 1

    # Early detection level: earliest level at which a failure was caught across the run
    early_level = "NONE"
    levels_with_failures = [
        e.test_level for e in ev_list
        if e.result in ("FAIL", "FAILED", "ERROR") and e.failures_detected > 0
    ]
    if TestLevel.TARGETED.value in levels_with_failures:
        early_level = TestLevel.TARGETED.value
    elif TestLevel.ADJACENT.value in levels_with_failures:
        early_level = TestLevel.ADJACENT.value
    elif TestLevel.SUBSYSTEM.value in levels_with_failures:
        early_level = TestLevel.SUBSYSTEM.value
    elif TestLevel.FULL.value in levels_with_failures:
        early_level = TestLevel.FULL.value

    return TestEvidenceMetrics(
        pass_rate=pass_rate,
        failure_rate=failure_rate,
        targeted_failure_mode=target_failure_mode,
        targeted_failure_count=targeted_count,
        targeted_failure_rate=targeted_rate,
        regressions_detected=regressions_detected,
        incomplete_fixes_detected=incomplete_fixes,
        targeted_behavior_confirmed=targeted_confirmed,
        adjacent_failures_discovered=adj_fails,
        subsystem_failures_discovered=sub_fails,
        full_suite_failures_discovered=full_fails,
        false_confidence_count=false_confidence,
        early_detection_level=early_level,
        clean_copy_verification_success=clean_copy_success,
    )


def build_testing_frontier(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Builds a transparent tabular comparison of testing variants along Quality vs Cost."""
    rows: List[Dict[str, Any]] = []
    for c in candidates:
        cid = c.get("candidate_id", "UNKNOWN")
        var = c.get("variant", cid)
        q: TestEvidenceMetrics = c["quality"]
        cost: TestCostMetrics = c["cost"]

        row = {
            "variant": var,
            "candidate_id": cid,
            "pass_rate": f"{q.pass_rate * 100:.1f}%",
            "target_failures": q.targeted_failure_count,
            "regressions_detected": q.regressions_detected,
            "false_confidence_avoided": q.false_confidence_count,
            "early_detection": q.early_detection_level,
            "test_commands": cost.total_test_commands,
            "tests_executed": cost.total_tests_executed,
            "runtime_ms": f"{cost.total_test_runtime_ms:.1f}",
            "full_suite_calls": cost.full_suite_commands,
        }
        rows.append(row)
    return rows


def render_testing_frontier_md(rows: List[Dict[str, Any]]) -> str:
    """Renders the Quality vs Cost frontier table in GitHub Markdown."""
    lines: List[str] = [
        "| Strategy | Candidate | Pass Rate | Target Failures | Regressions Caught | False Conf. Avoided | Early Detection | Test Cmds | Tests Run | Runtime (ms) | Full Suites |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in rows:
        lines.append(
            f"| `{r['variant']}` | `{r['candidate_id']}` | {r['pass_rate']} | {r['target_failures']} | "
            f"{r['regressions_detected']} | {r['false_confidence_avoided']} | `{r['early_detection']}` | "
            f"{r['test_commands']} | {r['tests_executed']} | {r['runtime_ms']} | {r['full_suite_calls']} |"
        )
    return "\n".join(lines)


build_test_quality_cost_frontier = build_testing_frontier
render_test_quality_cost_frontier_md = render_testing_frontier_md
