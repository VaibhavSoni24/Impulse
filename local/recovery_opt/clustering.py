"""Deterministic Recovery Pattern Clustering and Cluster Selection (Stage 35 Sections 8, 9).

Groups normalized RecoveryFailureRecord instances into deterministic RecoveryCluster objects.
Applies transparent lexicographic cluster selection:
1. eligible completed LIVE runs containing the pattern (descending)
2. unique affected tasks (descending)
3. recurrence count (descending)
4. loop count (descending)
5. recovery failure count (descending)
6. deterministic cluster_id (ascending)

When no actionable LIVE recovery pattern exists, returns selection_status = NO_ACTIONABLE_LIVE_RECOVERY.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from local.dashboard.models import EvidenceMode
from local.recovery_opt.models import (
    RecoveryCluster,
    RecoveryFailureRecord,
    RecoveryOutcome,
    RecoverySelectionStatus,
)


def _sanitize_slug(text: str) -> str:
    """Creates a deterministic filesystem/ID-safe slug."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    return text.strip("_")


def generate_recovery_cluster_key(record: RecoveryFailureRecord) -> tuple[str, str]:
    """Generates the grouping tuple for a recovery record: (pattern_type, canonical_signature)."""
    pat = (record.repeated_pattern or record.failure_class or "UNKNOWN").upper()
    sig = (record.failure_signature or "UNKNOWN_SIG").strip()
    return pat, sig


def generate_recovery_cluster_id(pattern_type: str, canonical_signature: str) -> str:
    """Generates a deterministic cluster identifier."""
    pat_slug = _sanitize_slug(pattern_type)
    sig_hash = hashlib.sha256(canonical_signature.encode("utf-8")).hexdigest()[:8]
    return f"rec_cls_{pat_slug}_{sig_hash}"


def cluster_recovery_failures(records: List[RecoveryFailureRecord]) -> List[RecoveryCluster]:
    """Deterministically clusters a list of RecoveryFailureRecords."""
    if not records:
        return []

    # Sort input records deterministically by task_id, run_id, failure_id
    sorted_records = sorted(
        records,
        key=lambda r: (r.task_id or "", r.run_id or "", r.failure_id or "", r.failure_signature or ""),
    )

    grouped: Dict[tuple[str, str], List[RecoveryFailureRecord]] = defaultdict(list)
    for rec in sorted_records:
        key = generate_recovery_cluster_key(rec)
        grouped[key].append(rec)

    clusters: List[RecoveryCluster] = []

    for (pat, sig), members in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        cid = generate_recovery_cluster_id(pat, sig)

        run_ids = sorted(list({r.run_id for r in members if r.run_id}))
        task_ids = sorted(list({r.task_id for r in members if r.task_id}))
        repos = sorted(list({r.repository for r in members if r.repository}))
        splits = sorted(list({r.split for r in members if r.split}))
        modes = sorted(list({r.evidence_mode for r in members if r.evidence_mode}))

        recurrence_count = len(members)
        success_count = len([r for r in members if r.recovery_success is True or r.recovery_outcome in [
            RecoveryOutcome.RECOVERED.value,
            RecoveryOutcome.RECOVERED_AFTER_RETRY.value,
            RecoveryOutcome.RECOVERED_AFTER_ALTERNATE_PATH.value,
        ]])
        fail_count = len([r for r in members if r.recovery_success is False or r.recovery_outcome == RecoveryOutcome.NOT_RECOVERED.value])
        loop_count = len([r for r in members if r.loop_detected or r.recovery_outcome == RecoveryOutcome.LOOP_DETECTED.value])

        # Earliest detection opportunity across members
        opps = [r.first_recovery_opportunity for r in members if r.first_recovery_opportunity is not None]
        earliest_opp = min(opps) if opps else None

        trace_refs: list[str] = []
        for r in members:
            trace_refs.extend(r.source_event_ids)
        trace_refs = sorted(list(set(trace_refs)))

        # Actionability
        eligible_runs = [r for r in members if r.is_actionable and r.evidence_mode != EvidenceMode.UNAVAILABLE.value]
        is_actionable = len(eligible_runs) > 0

        if is_actionable:
            action_reason = f"Contains {len(eligible_runs)} actionable failure records across {len(task_ids)} tasks."
        else:
            action_reason = "Non-actionable: all associated runs are unavailable, unexecuted, or infrastructure-blocked."

        rep_member = eligible_runs[0] if eligible_runs else members[0]

        cluster = RecoveryCluster(
            cluster_id=cid,
            pattern_type=pat,
            canonical_signature=sig,
            affected_runs=run_ids,
            affected_unique_tasks=task_ids,
            evidence_modes=modes,
            repositories=repos,
            splits=splits,
            recurrence_count=recurrence_count,
            successful_recovery_count=success_count,
            failed_recovery_count=fail_count,
            loop_count=loop_count,
            earliest_detection_opportunity=earliest_opp,
            representative_trace_references=trace_refs,
            actionable_status=is_actionable,
            actionability_reason=action_reason,
            representative_failure=rep_member.to_dict(),
        )
        clusters.append(cluster)

    # Sort clusters deterministically
    clusters.sort(key=lambda c: (c.pattern_type, c.cluster_id))
    return clusters


def select_highest_value_recovery_cluster(
    clusters: List[RecoveryCluster],
    allow_fixture: bool = False,
) -> Tuple[Optional[RecoveryCluster], RecoverySelectionStatus, str]:
    """Selects the highest-value recovery cluster using a transparent lexicographic policy (Stage 35 Section 9).

    Lexicographic order:
    1. eligible completed LIVE runs containing the pattern (descending)
    2. unique affected tasks (descending)
    3. recurrence count (descending)
    4. loop count (descending)
    5. recovery failure count (descending)
    6. deterministic cluster_id (ascending)

    When no actionable LIVE recovery pattern exists, returns NO_ACTIONABLE_LIVE_RECOVERY.
    """
    if not clusters:
        return (
            None,
            RecoverySelectionStatus.NO_PATTERNS_FOUND,
            "No recovery patterns were mined from evaluation sources.",
        )

    # Filter by evidence mode
    live_clusters = [
        c for c in clusters
        if c.actionable_status and EvidenceMode.LIVE.value in c.evidence_modes
    ]

    if not live_clusters:
        if allow_fixture:
            fixture_clusters = [
                c for c in clusters
                if c.actionable_status and EvidenceMode.FIXTURE.value in c.evidence_modes
            ]
            if fixture_clusters:
                # Rank fixture clusters lexicographically
                ranked = sorted(
                    fixture_clusters,
                    key=lambda c: (
                        -len(c.affected_unique_tasks),
                        -c.recurrence_count,
                        -c.loop_count,
                        -c.failed_recovery_count,
                        c.cluster_id,
                    ),
                )
                selected = ranked[0]
                return (
                    selected,
                    RecoverySelectionStatus.ACTIONABLE_RECOVERY_SELECTED,
                    f"Selected actionable FIXTURE cluster '{selected.cluster_id}' ({selected.pattern_type}).",
                )

        # Check if infrastructure only
        infra_only = all(
            EvidenceMode.UNAVAILABLE.value in c.evidence_modes
            for c in clusters
        )
        status = RecoverySelectionStatus.INFRASTRUCTURE_ONLY if infra_only else RecoverySelectionStatus.NO_ACTIONABLE_LIVE_RECOVERY
        return (
            None,
            status,
            "No actionable completed LIVE recovery pattern exists. Local environment has not executed live competition inference.",
        )

    # Rank live clusters lexicographically
    ranked_live = sorted(
        live_clusters,
        key=lambda c: (
            -len([r for r in c.affected_runs]),
            -len(c.affected_unique_tasks),
            -c.recurrence_count,
            -c.loop_count,
            -c.failed_recovery_count,
            c.cluster_id,
        ),
    )
    selected = ranked_live[0]
    return (
        selected,
        RecoverySelectionStatus.ACTIONABLE_RECOVERY_SELECTED,
        f"Selected highest-value actionable LIVE cluster '{selected.cluster_id}' ({selected.pattern_type}) "
        f"affecting {len(selected.affected_unique_tasks)} tasks across {len(selected.affected_runs)} runs.",
    )
