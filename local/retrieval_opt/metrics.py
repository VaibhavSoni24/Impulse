"""Retrieval Quality and Cost Metrics Calculation Engine (Stage 33 Sections 12, 14, 15, 16).

Provides:
- Quantitative cost calculation (calls, shares, durations, entities, proxy gain)
- Quantitative quality calculation (pass rate, targeted failure rate, transitions)
- Non-opaque Quality-vs-Cost Pareto frontier evaluation
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from local.fdd.models import FailureRecord
from local.retrieval_opt.models import (
    RetrievalCostMetrics,
    RetrievalEvent,
    RetrievalQualityMetrics,
    RetrievalTaskPairOutcome,
    RetrievalType,
    TaskTransition,
)


def compute_retrieval_cost_metrics(
    events: List[RetrievalEvent],
    total_agent_tool_calls: Optional[int] = None,
    total_runtime_ms: Optional[float] = None,
    turns: Optional[int] = None,
) -> RetrievalCostMetrics:
    """Computes comprehensive cost and information-gain proxy metrics from retrieval events."""
    retrieval_call_count = len(events)
    semantic_calls = sum(1 for e in events if e.retrieval_type == RetrievalType.SEMANTIC.value)
    neighbor_calls = sum(1 for e in events if e.retrieval_type == RetrievalType.NEIGHBORS.value)
    subgraph_calls = sum(1 for e in events if e.retrieval_type == RetrievalType.SUBGRAPH.value)
    cache_hit_count = sum(1 for e in events if e.cache_hit)

    durations = [e.retrieval_duration_ms for e in events if e.retrieval_duration_ms > 0]
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

    # Entities and unique sets
    all_entities: List[str] = []
    unique_entities_set: set[str] = set()
    all_files_set: set[str] = set()
    total_token_growth = 0

    for e in events:
        for ent in e.returned_entities:
            all_entities.append(ent)
            unique_entities_set.add(ent)
        for f in e.source_files_exposed:
            all_files_set.add(f)
        total_token_growth += e.context_token_growth

    retrieved_entities = len(all_entities)
    unique_entities = len(unique_entities_set)
    duplicate_entities = retrieved_entities - unique_entities
    source_files_exposed = len(all_files_set)

    # Share of tool calls
    tool_call_share: Optional[float] = None
    if total_agent_tool_calls is not None and total_agent_tool_calls > 0:
        tool_call_share = round(retrieval_call_count / total_agent_tool_calls, 4)

    # Cache hit ratio
    cache_hit_ratio: Optional[float] = None
    if retrieval_call_count > 0:
        cache_hit_ratio = round(cache_hit_count / retrieval_call_count, 4)

    # Information-gain proxies
    unique_entities_per_call: Optional[float] = None
    unique_files_per_call: Optional[float] = None
    if retrieval_call_count > 0:
        unique_entities_per_call = round(unique_entities / retrieval_call_count, 2)
        unique_files_per_call = round(source_files_exposed / retrieval_call_count, 2)

    return RetrievalCostMetrics(
        retrieval_call_count=retrieval_call_count,
        semantic_calls=semantic_calls,
        neighbor_calls=neighbor_calls,
        subgraph_calls=subgraph_calls,
        retrieval_tool_call_share=tool_call_share,
        mean_retrieval_duration_ms=round(mean_dur, 2) if mean_dur is not None else None,
        median_retrieval_duration_ms=round(median_dur, 2) if median_dur is not None else None,
        p95_retrieval_duration_ms=round(p95_dur, 2) if p95_dur is not None else None,
        retrieved_entities=retrieved_entities,
        unique_entities=unique_entities,
        duplicate_entities=duplicate_entities,
        source_files_exposed=source_files_exposed,
        total_context_growth_tokens=total_token_growth if total_token_growth > 0 else None,
        total_agent_tool_calls=total_agent_tool_calls,
        total_runtime_ms=total_runtime_ms,
        turns=turns,
        cache_hit_count=cache_hit_count,
        cache_hit_ratio=cache_hit_ratio,
        unique_entities_per_retrieval_call=unique_entities_per_call,
        unique_files_per_retrieval_call=unique_files_per_call,
    )


def compute_retrieval_quality_metrics(
    candidate_records: List[FailureRecord],
    target_failure_mode: str,
    paired_outcomes: Optional[List[RetrievalTaskPairOutcome]] = None,
    clean_copy_success: bool = True,
    recovery_success_count: int = 0,
) -> RetrievalQualityMetrics:
    """Computes task-solving quality metrics from candidate failure records and paired outcomes."""
    total_tasks = len(candidate_records)
    if total_tasks == 0:
        return RetrievalQualityMetrics(
            pass_rate=0.0,
            failure_rate=0.0,
            targeted_failure_mode=target_failure_mode,
            targeted_failure_count=0,
            targeted_failure_rate=0.0,
            localization_failure_count=0,
            clean_copy_verification_success=clean_copy_success,
        )

    pass_count = sum(1 for r in candidate_records if r.success is True)
    fail_count = sum(1 for r in candidate_records if r.success is False)

    targeted_count = sum(
        1 for r in candidate_records
        if not r.success and (
            r.failure_category == target_failure_mode
            or getattr(r, "error_type", None) == target_failure_mode
        )
    )

    # Localization failures (where failure_category or error_type relates to search/localization)
    localization_count = sum(
        1 for r in candidate_records
        if not r.success and any(
            k in (r.failure_category or "").upper()
            or k in (getattr(r, "error_type", "") or "").upper()
            for k in ["LOCALIZATION", "SEARCH", "SYMBOL_NOT_FOUND", "MISSING_CONTEXT"]
        )
    )

    fail_to_pass = 0
    pass_to_fail = 0
    fail_to_other = 0
    unchanged = 0

    if paired_outcomes:
        for p in paired_outcomes:
            if p.transition == TaskTransition.FAIL_TO_PASS:
                fail_to_pass += 1
            elif p.transition == TaskTransition.PASS_TO_FAIL:
                pass_to_fail += 1
            elif p.transition == TaskTransition.FAIL_TO_OTHER_FAIL:
                fail_to_other += 1
            elif p.transition in (TaskTransition.FAIL_UNCHANGED, TaskTransition.PASS_UNCHANGED):
                unchanged += 1

    return RetrievalQualityMetrics(
        pass_rate=round(pass_count / total_tasks, 4),
        failure_rate=round(fail_count / total_tasks, 4),
        targeted_failure_mode=target_failure_mode,
        targeted_failure_count=targeted_count,
        targeted_failure_rate=round(targeted_count / total_tasks, 4),
        localization_failure_count=localization_count,
        fail_to_pass_count=fail_to_pass,
        pass_to_fail_count=pass_to_fail,
        fail_to_other_fail_count=fail_to_other,
        unchanged_failure_count=unchanged,
        clean_copy_verification_success=clean_copy_success,
        recovery_success_count=recovery_success_count,
    )


def build_quality_cost_frontier(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Builds a transparent tabular comparison of variants along the Quality vs Cost frontier.

    Does NOT calculate an opaque single score. Exposes measured dimensions directly.
    """
    rows: List[Dict[str, Any]] = []
    for c in candidates:
        vid = c.get("candidate_id", "UNKNOWN")
        var = c.get("variant", vid)
        q: RetrievalQualityMetrics = c["quality"]
        cost: RetrievalCostMetrics = c["cost"]

        row = {
            "variant": var,
            "candidate_id": vid,
            "pass_rate": f"{q.pass_rate * 100:.1f}%",
            "target_failure_count": q.targeted_failure_count,
            "retrieval_calls": cost.retrieval_call_count,
            "mean_duration_ms": (
                f"{cost.mean_retrieval_duration_ms:.1f}"
                if cost.mean_retrieval_duration_ms is not None
                else "N/A"
            ),
            "unique_entities": cost.unique_entities,
            "context_growth_tokens": (
                str(cost.total_context_growth_tokens)
                if cost.total_context_growth_tokens is not None
                else "N/A"
            ),
            "cache_hit_ratio": (
                f"{cost.cache_hit_ratio * 100:.1f}%"
                if cost.cache_hit_ratio is not None
                else "N/A"
            ),
            "info_gain_proxy": (
                f"{cost.unique_entities_per_retrieval_call:.2f}"
                if cost.unique_entities_per_retrieval_call is not None
                else "N/A"
            ),
        }
        rows.append(row)
    return rows


def render_quality_cost_frontier_md(rows: List[Dict[str, Any]]) -> str:
    """Renders the Quality/Cost frontier table in clean GitHub Markdown."""
    lines: List[str] = [
        "| Variant | Candidate | Pass Rate | Target Failures | Retrieval Calls | Mean Duration (ms) | Unique Entities | Context Growth | Cache Hit % | Info Gain Proxy |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in rows:
        lines.append(
            f"| `{r['variant']}` | `{r['candidate_id']}` | {r['pass_rate']} | {r['target_failure_count']} | "
            f"{r['retrieval_calls']} | {r['mean_duration_ms']} | {r['unique_entities']} | "
            f"{r['context_growth_tokens']} | {r['cache_hit_ratio']} | {r['info_gain_proxy']} |"
        )
    return "\n".join(lines)
