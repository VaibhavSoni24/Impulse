"""Deterministic Reporting and Manifest Generation for FDD (Stage 31 Sections 15 & 16).

Produces structured, reproducible experiment artifacts in experiments/fdd/<intervention-id>/:
- manifest.json: Cryptographic hashes and state tracking
- cluster.json: Root failure cluster snapshot
- intervention.json: Exact typed intervention
- result.json: Quantitative delta and decision record
- report.md: Human-readable markdown audit report
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.fdd.models import (
    FDDExperimentManifest,
    FDDRunDelta,
    FailureCluster,
    FailureRecord,
    Intervention,
    PromotionDecision,
)


def _compute_sha256(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def generate_fdd_report(
    manifest: FDDExperimentManifest,
    intervention: Intervention,
    cluster: Optional[FailureCluster] = None,
    delta: Optional[FDDRunDelta] = None,
) -> str:
    """Generates the authoritative human-readable markdown experiment report."""
    lines: List[str] = [
        "# Failure-Driven Experiment",
        "",
        "## Baseline",
        f"- **Candidate:** `{manifest.baseline_candidate}`",
        f"- **Commit:** `{manifest.git_commit or 'HEAD'}`",
        f"- **Split Manifest SHA-256:** `{manifest.split_manifest_sha256 or 'N/A'}`",
        f"- **Evidence Mode:** `{manifest.evidence_mode}`",
        "",
        "## Target Failure",
        f"- **Failure Signature:** `{manifest.target_failure_mode}`",
        f"- **Intervention ID:** `{intervention.intervention_id}`",
        "",
        "## Evidence",
        f"- **Source Cluster ID:** `{cluster.cluster_id if cluster else (manifest.cluster_id or 'None')}`",
        f"- **Affected Runs:** {cluster.affected_runs_count if cluster else 'N/A'}",
        f"- **Eligible Completed Runs:** {cluster.eligible_completed_run_count if cluster else 'N/A'}",
        f"- **Affected Tasks:** {cluster.unique_tasks_count if cluster else 'N/A'}",
        f"- **Repositories:** {', '.join(cluster.repositories) if cluster and cluster.repositories else 'N/A'}",
        "",
        "## Cluster",
        f"- **Actionable:** {cluster.is_actionable if cluster else False}",
        f"- **Actionability Reason:** {cluster.actionability_reason if cluster else 'No active cluster'}",
        f"- **Representative Signature:** `{cluster.signature if cluster else 'N/A'}`",
        "",
        "## Hypothesis",
        f"> {intervention.hypothesis}",
        "",
        f"- **Expected Behavior Change:** {intervention.expected_behavior_change}",
        f"- **Scope:** `{intervention.intervention_scope}`",
        f"- **Changed Dimensions:** `{', '.join(intervention.changed_dimensions)}`",
        "",
        "## Intervention",
        f"- **Candidate Created:** `{manifest.candidate_id}`",
        f"- **Affected Files:** {', '.join(intervention.affected_files) if intervention.affected_files else 'None'}",
        f"- **Rejection Condition:** {intervention.rejection_condition}",
        "",
        "## Smoke Result",
        f"- **Smoke Tasks:** {', '.join(intervention.smoke_tasks) if intervention.smoke_tasks else 'None'}",
        f"- **Smoke Status:** {'PASSED' if manifest.smoke_passed is True else ('FAILED' if manifest.smoke_passed is False else 'SKIPPED')}",
        "",
        "## Validation Result",
        f"- **Validation Split:** `{intervention.validation_split}`",
        f"- **Validation Status:** {'PASSED' if manifest.validation_passed is True else ('FAILED' if manifest.validation_passed is False else 'UNEXECUTED')}",
        "",
        "## Held-Out Result",
        f"- **Held-Out Evaluated:** {'YES' if manifest.held_out_passed is not None else 'NO (held-out protected / not required)'}",
        f"- **Held-Out Status:** {'PASSED' if manifest.held_out_passed is True else ('REGRESSED' if manifest.held_out_passed is False else 'UNEXECUTED')}",
        f"- **Held-Out Lock SHA-256:** `{manifest.held_out_lock_sha256 or 'N/A'}`",
        "",
        "## Targeted Failure Delta",
    ]

    if delta and delta.targeted_reduction is not None:
        lines.extend([
            f"- **Target Mode:** `{delta.target_failure_mode}`",
            f"- **Baseline Failures:** {delta.baseline_failure_count}",
            f"- **Candidate Failures:** {delta.candidate_failure_count}",
            f"- **Targeted Reduction:** {delta.targeted_reduction}",
            f"- **Pass Rate Delta:** {f'{delta.pass_rate_delta:+.2%}' if delta.pass_rate_delta is not None else 'N/A'}",
        ])
    else:
        lines.extend([
            f"- **Target Mode:** `{manifest.target_failure_mode}`",
            "- **Baseline Failures:** N/A",
            "- **Candidate Failures:** N/A",
            "- **Targeted Reduction:** N/A",
        ])

    lines.extend([
        "",
        "## Collateral Effects",
    ])

    if delta and (delta.collateral_regressions or delta.collateral_improvements):
        if delta.collateral_regressions:
            lines.append("- **Collateral Regressions:**")
            for cat, cnt in sorted(delta.collateral_regressions.items()):
                lines.append(f"  - `{cat}`: +{cnt}")
        else:
            lines.append("- **Collateral Regressions:** None observed (0)")

        if delta.collateral_improvements:
            lines.append("- **Collateral Improvements:**")
            for cat, cnt in sorted(delta.collateral_improvements.items()):
                lines.append(f"  - `{cat}`: -{cnt}")
    else:
        lines.append("- **Collateral Regressions:** None observed / unmeasured")

    lines.extend([
        "",
        "## Decision",
        f"- **Authoritative Decision:** `{manifest.decision.value if isinstance(manifest.decision, PromotionDecision) else manifest.decision}`",
        f"- **Decision Rationale:** {manifest.decision_rationale or 'N/A'}",
        "",
        "## Reproducibility",
        f"- **Experiment Directory:** `experiments/fdd/{intervention.intervention_id}/`",
        f"- **Intervention Manifest:** `manifest.json`",
    ])

    for artifact, ahash in sorted(manifest.artifact_hashes.items()):
        if artifact != "report.md":
            lines.append(f"- **{artifact} SHA-256:** `{ahash}`")

    lines.append("")
    return "\n".join(lines)


def save_fdd_experiment_artifacts(
    experiment_dir: Path | str,
    manifest: FDDExperimentManifest,
    intervention: Intervention,
    cluster: Optional[FailureCluster] = None,
    delta: Optional[FDDRunDelta] = None,
    smoke_records: Optional[List[FailureRecord]] = None,
    validation_records: Optional[List[FailureRecord]] = None,
    held_out_records: Optional[List[FailureRecord]] = None,
) -> Path:
    """Deterministically saves and hashes all FDD experiment artifacts."""
    exp_path = Path(experiment_dir)
    exp_path.mkdir(parents=True, exist_ok=True)

    # 1. Save intervention.json
    int_path = exp_path / "intervention.json"
    with open(int_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(intervention.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")
    manifest.artifact_hashes["intervention.json"] = _compute_sha256(int_path.read_bytes())

    # 2. Save cluster.json
    cls_path = exp_path / "cluster.json"
    cls_dict = cluster.to_dict() if cluster else {"cluster_id": manifest.cluster_id or "NONE", "is_actionable": False}
    with open(cls_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cls_dict, f, indent=2, sort_keys=True)
        f.write("\n")
    manifest.artifact_hashes["cluster.json"] = _compute_sha256(cls_path.read_bytes())

    # 3. Save result.json
    res_path = exp_path / "result.json"
    res_data = {
        "decision": manifest.decision.value if isinstance(manifest.decision, PromotionDecision) else str(manifest.decision),
        "decision_rationale": manifest.decision_rationale,
        "delta": delta.to_dict() if delta else None,
        "smoke_passed": manifest.smoke_passed,
        "validation_passed": manifest.validation_passed,
        "held_out_passed": manifest.held_out_passed,
    }
    with open(res_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res_data, f, indent=2, sort_keys=True)
        f.write("\n")
    manifest.artifact_hashes["result.json"] = _compute_sha256(res_path.read_bytes())

    # 4. Save report.md
    report_content = generate_fdd_report(manifest, intervention, cluster, delta)
    rep_path = exp_path / "report.md"
    with open(rep_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report_content)
    manifest.artifact_hashes["report.md"] = _compute_sha256(rep_path.read_bytes())

    # 5. Save manifest.json
    man_path = exp_path / "manifest.json"
    with open(man_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")

    # 6. Save raw run records if provided
    if smoke_records:
        smoke_dir = exp_path / "smoke"
        smoke_dir.mkdir(exist_ok=True)
        with open(smoke_dir / "records.jsonl", "w", encoding="utf-8") as f:
            for r in smoke_records:
                f.write(json.dumps(r.to_dict(), sort_keys=True) + "\n")

    if validation_records:
        val_dir = exp_path / "validation"
        val_dir.mkdir(exist_ok=True)
        with open(val_dir / "records.jsonl", "w", encoding="utf-8") as f:
            for r in validation_records:
                f.write(json.dumps(r.to_dict(), sort_keys=True) + "\n")

    if held_out_records:
        ho_dir = exp_path / "held_out"
        ho_dir.mkdir(exist_ok=True)
        with open(ho_dir / "records.jsonl", "w", encoding="utf-8") as f:
            for r in held_out_records:
                f.write(json.dumps(r.to_dict(), sort_keys=True) + "\n")

    return exp_path
