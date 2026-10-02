"""Runtime acceptability evaluation for Stage 44 promotion gate.

Evaluates:
- Average, median, and maximum execution latency
- Hard ceiling timeouts and budget exhaustion
- Tool call counts and execution overhead
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

from local.promotion.models import (
    EvidenceMode,
    GateDimensionStatus,
    RuntimeEvaluationResult,
)
from local.versioning.models import CandidateManifest

DEFAULT_BUDGET_LIMIT_MS = 900_000.0  # 15 minutes default harness timeout


def evaluate_runtime(
    candidate_manifest: CandidateManifest,
    candidate_runs: List[Dict[str, Any]],
    evidence_mode: str = EvidenceMode.UNAVAILABLE.value,
    budget_limit_ms_override: Optional[float] = None,
) -> RuntimeEvaluationResult:
    """Evaluates whether candidate execution satisfies runtime constraints."""
    if evidence_mode != EvidenceMode.LIVE.value:
        return RuntimeEvaluationResult(
            dimension_status=GateDimensionStatus.UNKNOWN.value,
            avg_runtime_ms=None,
            median_runtime_ms=None,
            max_runtime_ms=None,
            budget_limit_ms=budget_limit_ms_override or DEFAULT_BUDGET_LIMIT_MS,
            tool_call_count=None,
            budget_violated=False,
            evidence_mode=evidence_mode,
            notes=f"Runtime acceptability requires LIVE benchmark execution data (current: {evidence_mode}).",
        )

    if not candidate_runs:
        return RuntimeEvaluationResult(
            dimension_status=GateDimensionStatus.UNKNOWN.value,
            avg_runtime_ms=None,
            median_runtime_ms=None,
            max_runtime_ms=None,
            budget_limit_ms=budget_limit_ms_override or DEFAULT_BUDGET_LIMIT_MS,
            tool_call_count=None,
            budget_violated=False,
            evidence_mode=evidence_mode,
            notes="No run records available to measure candidate runtime.",
        )

    # Determine budget limit
    configured_timeout_sec = candidate_manifest.runtime_settings.get("timeout_seconds")
    if budget_limit_ms_override:
        budget_limit_ms = budget_limit_ms_override
    elif configured_timeout_sec is not None:
        budget_limit_ms = float(configured_timeout_sec) * 1000.0
    else:
        budget_limit_ms = DEFAULT_BUDGET_LIMIT_MS

    latencies_ms: List[float] = []
    tool_calls: List[int] = []
    timeouts_detected = 0

    for r in candidate_runs:
        sec = r.get("elapsed_seconds")
        if sec is not None:
            latencies_ms.append(float(sec) * 1000.0)
        tc = r.get("tool_calls")
        if tc is not None:
            tool_calls.append(int(tc))
        if str(r.get("status") or "").lower() == "timeout" or str(r.get("termination_reason") or "").lower() == "timeout":
            timeouts_detected += 1

    if not latencies_ms:
        return RuntimeEvaluationResult(
            dimension_status=GateDimensionStatus.UNKNOWN.value,
            avg_runtime_ms=None,
            median_runtime_ms=None,
            max_runtime_ms=None,
            budget_limit_ms=budget_limit_ms,
            tool_call_count=sum(tool_calls) if tool_calls else None,
            budget_violated=False,
            evidence_mode=evidence_mode,
            notes="Completed runs did not record elapsed timing.",
        )

    avg_ms = round(statistics.mean(latencies_ms), 1)
    median_ms = round(statistics.median(latencies_ms), 1)
    max_ms = round(max(latencies_ms), 1)
    tot_tools = sum(tool_calls) if tool_calls else None

    budget_violated = max_ms > budget_limit_ms or timeouts_detected > 0
    if budget_violated:
        status = GateDimensionStatus.FAIL.value
        notes = (
            f"Runtime budget violation: max run latency {max_ms:.1f}ms exceeds {budget_limit_ms:.1f}ms "
            f"(timeouts: {timeouts_detected})."
        )
    else:
        status = GateDimensionStatus.PASS.value
        notes = f"Acceptable runtime: avg={avg_ms:.1f}ms, max={max_ms:.1f}ms <= budget={budget_limit_ms:.1f}ms."

    return RuntimeEvaluationResult(
        dimension_status=status,
        avg_runtime_ms=avg_ms,
        median_runtime_ms=median_ms,
        max_runtime_ms=max_ms,
        budget_limit_ms=budget_limit_ms,
        tool_call_count=tot_tools,
        budget_violated=budget_violated,
        evidence_mode=evidence_mode,
        notes=notes,
    )
