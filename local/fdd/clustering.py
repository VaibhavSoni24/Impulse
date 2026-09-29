"""Deterministic Failure Clustering (Stage 31 Section 5).

Groups normalized FailureRecord instances into deterministic FailureCluster objects
using canonical failure categories, evaluator failure stages, and termination signatures.
Ensures deterministic cluster IDs, member ordering, and clear separation between
actionable and infrastructure-limited failures.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import re
from typing import Any, Dict, List, Optional

from local.fdd.models import FailureCluster, FailureRecord


def _sanitize_slug(text: str) -> str:
    """Creates a deterministic filesystem/ID-safe slug."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    return text.strip("_")


def generate_cluster_key(record: FailureRecord) -> tuple[str, str, str]:
    """Generates the grouping tuple for a failure record: (category, stage, signature)."""
    cat = (record.failure_category or "UNKNOWN").upper()
    stage = (record.failure_stage or "UNKNOWN").upper()

    # Extract primary termination signature
    raw_term = (record.termination_reason or "").strip()
    if raw_term:
        # Keep first meaningful line or phrase
        sig = raw_term.split("\n")[0][:100].strip()
    else:
        sig = f"{cat}_{stage}"

    return cat, stage, sig


def generate_cluster_id(cat: str, stage: str, sig: str) -> str:
    """Generates a deterministic cluster identifier."""
    base_slug = f"{_sanitize_slug(cat)}_{_sanitize_slug(stage)}"
    # Add short hash of signature to guarantee uniqueness without runaway lengths
    sig_hash = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:8]
    return f"cls_{base_slug}_{sig_hash}"


def cluster_failures(records: List[FailureRecord]) -> List[FailureCluster]:
    """Deterministically clusters a list of FailureRecords.

    Guarantees:
    - Same input records in any order produce identical cluster contents.
    - Output cluster list is deterministically sorted.
    - Strict isolation of actionable (live/fixture cognitive) vs non-actionable failures.
    """
    if not records:
        return []

    # Deterministically pre-sort records by task_id, run_id
    sorted_records = sorted(
        records,
        key=lambda r: (r.task_id or "", r.run_id or "", r.source_record_reference or ""),
    )

    grouped: Dict[tuple[str, str, str], List[FailureRecord]] = defaultdict(list)
    for rec in sorted_records:
        key = generate_cluster_key(rec)
        grouped[key].append(rec)

    clusters: List[FailureCluster] = []

    for (cat, stage, sig), members in grouped.items():
        cid = generate_cluster_id(cat, stage, sig)

        run_ids = sorted(list({r.run_id for r in members if r.run_id}))
        task_ids = sorted(list({r.task_id for r in members if r.task_id}))
        repos = sorted(list({r.repository for r in members if r.repository}))
        splits = sorted(list({r.split for r in members if r.split}))
        evidence_modes = sorted(list({r.evidence_mode for r in members if r.evidence_mode}))

        eligible_runs = [r for r in members if r.is_actionable]
        eligible_count = len(eligible_runs)

        if eligible_count > 0:
            is_actionable = True
            action_reason = f"Contains {eligible_count} actionable completed failure runs across {len(task_ids)} tasks."
        else:
            is_actionable = False
            action_reason = (
                f"Non-actionable: {len(members)} runs are all unexecuted, unavailable, "
                "or infrastructure-blocked."
            )

        # Pick representative failure deterministically
        rep_member = eligible_runs[0] if eligible_runs else members[0]
        rep_dict = rep_member.to_dict()

        cluster = FailureCluster(
            cluster_id=cid,
            signature=sig,
            failure_category=cat,
            failure_stage=stage,
            termination_reason_sample=members[0].termination_reason,
            affected_runs_count=len(members),
            unique_tasks_count=len(task_ids),
            eligible_completed_run_count=eligible_count,
            evidence_modes=evidence_modes,
            repositories=repos,
            splits=splits,
            run_ids=run_ids,
            task_ids=task_ids,
            representative_failure=rep_dict,
            is_actionable=is_actionable,
            actionability_reason=action_reason,
        )
        clusters.append(cluster)

    # Sort clusters deterministically
    clusters.sort(
        key=lambda c: (
            c.eligible_completed_run_count,
            c.unique_tasks_count,
            c.affected_runs_count,
            c.cluster_id,
        ),
        reverse=True,
    )

    return clusters
