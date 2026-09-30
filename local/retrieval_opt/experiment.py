"""Retrieval Experiment Orchestration and Execution Engine (Stage 33 Sections 5, 27, 28).

Integrates:
- Baseline R0 establishment
- R1..R4 candidate creation and single-dimension validation
- Policy diffing and artifact hashing
- Trace logging and diagnostics
- Quality and cost metrics calculation
- Paired per-task outcome comparisons
- Gating and promotion decisions via FDD loop
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.fdd.gates import compute_run_delta, evaluate_promotion_gate
from local.fdd.models import (
    FDDRunDelta,
    FailureRecord,
    Intervention,
    InterventionScope,
    PromotionDecision,
)
from local.retrieval_opt.diff import (
    RetrievalPolicyDiff,
    compute_retrieval_policy_diff,
    render_retrieval_policy_diff_md,
)
from local.retrieval_opt.metrics import (
    compute_retrieval_cost_metrics,
    compute_retrieval_quality_metrics,
)
from local.retrieval_opt.models import (
    RetrievalCandidateManifest,
    RetrievalCostMetrics,
    RetrievalDiagnostics,
    RetrievalEvent,
    RetrievalHypothesis,
    RetrievalPolicy,
    RetrievalQualityMetrics,
    RetrievalTaskPairOutcome,
    RetrievalVariant,
)
from local.retrieval_opt.paired import (
    compute_retrieval_paired_comparison,
    save_paired_results_csv,
    save_paired_results_jsonl,
)
from local.retrieval_opt.policy import build_r0_baseline_policy, get_canonical_policy
from local.retrieval_opt.reporting import generate_retrieval_experiment_report
from local.retrieval_opt.trace import RetrievalTraceCollector
from local.retrieval_opt.validator import (
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_TOPOLOGY_ID,
    RetrievalValidationError,
    validate_retrieval_candidate_integrity,
)


def _compute_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class RetrievalExperimentManager:
    """Manages candidate creation, diffing, execution, and artifact auditing for retrieval experiments."""

    def __init__(
        self,
        retrieval_base_dir: Path | str = Path("experiments/retrieval"),
        repo_root: Optional[Path | str] = None,
        benchmark_split: str = "validation",
    ) -> None:
        self.retrieval_base_dir = Path(retrieval_base_dir)
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.benchmark_split = benchmark_split

    def ensure_r0_baseline(
        self,
        git_commit: str = "",
        evidence_mode: str = "UNAVAILABLE",
    ) -> RetrievalCandidateManifest:
        """Ensures that the immutable R0 baseline exists under experiments/retrieval/R0/."""
        r0_dir = self.retrieval_base_dir / "R0"
        r0_manifest_path = r0_dir / "manifest.json"
        if r0_manifest_path.is_file():
            with open(r0_manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RetrievalCandidateManifest.from_dict(data)

        r0_dir.mkdir(parents=True, exist_ok=True)
        policy = build_r0_baseline_policy()
        pol_hash = policy.compute_policy_hash()

        # Save policy.json
        pol_path = r0_dir / "policy.json"
        with open(pol_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(policy.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        # Save empty baseline trace
        trace_path = r0_dir / "retrieval_trace.jsonl"
        with open(trace_path, "w", encoding="utf-8", newline="\n") as f:
            pass

        manifest = RetrievalCandidateManifest(
            candidate_id="R0",
            parent_candidate_id=None,
            retrieval_variant=RetrievalVariant.R0.value,
            retrieval_policy_hash=pol_hash,
            target_failure_mode="BASELINE",
            benchmark_split=self.benchmark_split,
            evidence_mode=evidence_mode,
            model_id=EXPECTED_MODEL_ID,
            topology_id=EXPECTED_TOPOLOGY_ID,
            prompt_id="P0",
            prompt_sha256=EXPECTED_P0_PROMPT_SHA256,
            created_from_commit=git_commit,
            experiment_id="exp-retrieval-r0-baseline",
            decision="PROMOTED",
            decision_rationale="Immutable baseline R0 established (no semantic/graph retrieval).",
            artifact_hashes={
                "policy.json": _compute_sha256(pol_path.read_bytes()),
                "retrieval_trace.jsonl": _compute_sha256(trace_path.read_bytes()),
            },
        )

        quality = RetrievalQualityMetrics(
            pass_rate=0.0,
            failure_rate=1.0 if evidence_mode != "UNAVAILABLE" else 0.0,
            targeted_failure_mode="BASELINE",
            targeted_failure_count=0,
            targeted_failure_rate=0.0,
            localization_failure_count=0,
        )
        cost = RetrievalCostMetrics(
            retrieval_call_count=0,
            semantic_calls=0,
            neighbor_calls=0,
            subgraph_calls=0,
            retrieved_entities=0,
            unique_entities=0,
            duplicate_entities=0,
            source_files_exposed=0,
        )

        # Save metrics.json
        met_path = r0_dir / "metrics.json"
        with open(met_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"quality": quality.to_dict(), "cost": cost.to_dict()}, f, indent=2, sort_keys=True)
            f.write("\n")
        manifest.artifact_hashes["metrics.json"] = _compute_sha256(met_path.read_bytes())

        # Generate report.md
        diff = compute_retrieval_policy_diff(policy, policy)
        report_text = generate_retrieval_experiment_report(
            manifest=manifest,
            diff=diff,
            quality=quality,
            cost=cost,
            diagnostics=RetrievalDiagnostics(),
            paired_outcomes=[],
            validation_passed=True,
        )
        rep_path = r0_dir / "report.md"
        with open(rep_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(report_text)
        manifest.artifact_hashes["report.md"] = _compute_sha256(rep_path.read_bytes())

        # Save final manifest
        with open(r0_manifest_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        return manifest

    def create_candidate(
        self,
        candidate_id: str,
        parent_candidate_id: str,
        policy: RetrievalPolicy,
        hypothesis: Optional[RetrievalHypothesis],
        source_failure_cluster_id: Optional[str] = None,
        git_commit: str = "",
        evidence_mode: str = "UNAVAILABLE",
    ) -> Tuple[RetrievalCandidateManifest, RetrievalPolicyDiff]:
        """Creates and validates an isolated retrieval candidate R(n)."""
        cand_dir = self.retrieval_base_dir / candidate_id
        if cand_dir.exists():
            raise FileExistsError(f"Retrieval candidate {candidate_id} already exists at {cand_dir}")

        # Ensure parent exists
        parent_dir = self.retrieval_base_dir / parent_candidate_id
        if parent_candidate_id == "R0" and not parent_dir.exists():
            self.ensure_r0_baseline(git_commit=git_commit, evidence_mode=evidence_mode)

        parent_policy_file = parent_dir / "policy.json"
        if not parent_policy_file.is_file():
            raise FileNotFoundError(f"Parent policy file not found: {parent_policy_file}")

        with open(parent_policy_file, "r", encoding="utf-8") as f:
            parent_policy = RetrievalPolicy.from_dict(json.load(f))

        diff = compute_retrieval_policy_diff(parent_policy, policy)

        policy_hash = policy.compute_policy_hash()
        manifest = RetrievalCandidateManifest(
            candidate_id=candidate_id,
            parent_candidate_id=parent_candidate_id,
            retrieval_variant=policy.variant,
            retrieval_policy_hash=policy_hash,
            source_failure_cluster_id=source_failure_cluster_id,
            target_failure_mode=hypothesis.target_failure if hypothesis else "UNKNOWN",
            hypothesis=hypothesis,
            benchmark_split=self.benchmark_split,
            evidence_mode=evidence_mode,
            model_id=EXPECTED_MODEL_ID,
            topology_id=EXPECTED_TOPOLOGY_ID,
            prompt_id="P0",
            prompt_sha256=EXPECTED_P0_PROMPT_SHA256,
            created_from_commit=git_commit,
            experiment_id=f"exp-retrieval-{candidate_id.lower()}",
            decision="PROPOSED",
        )

        cand_dir.mkdir(parents=True, exist_ok=True)

        # Write policy.json
        cand_pol_path = cand_dir / "policy.json"
        with open(cand_pol_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(policy.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")
        manifest.artifact_hashes["policy.json"] = _compute_sha256(cand_pol_path.read_bytes())

        # Validate candidate
        is_valid, errors = validate_retrieval_candidate_integrity(
            manifest=manifest,
            policy=policy,
            repo_root=self.repo_root,
        )
        if not is_valid:
            import shutil
            shutil.rmtree(cand_dir, ignore_errors=True)
            raise RetrievalValidationError(f"Retrieval candidate validation failed: {'; '.join(errors)}")

        # Save initial manifest
        man_path = cand_dir / "manifest.json"
        with open(man_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        return manifest, diff

    def record_experiment_results(
        self,
        candidate_id: str,
        manifest: RetrievalCandidateManifest,
        policy: RetrievalPolicy,
        diff: RetrievalPolicyDiff,
        events: List[RetrievalEvent],
        baseline_records: Optional[List[FailureRecord]] = None,
        candidate_records: Optional[List[FailureRecord]] = None,
        baseline_events: Optional[List[RetrievalEvent]] = None,
        smoke_passed: Optional[bool] = None,
        validation_passed: Optional[bool] = None,
        held_out_passed: Optional[bool] = None,
        decision: str = "INCONCLUSIVE",
        decision_rationale: str = "",
        total_agent_tool_calls: Optional[int] = None,
        total_runtime_ms: Optional[float] = None,
        turns: Optional[int] = None,
    ) -> Path:
        """Records complete experiment artifacts, metrics, paired comparisons, and audit report."""
        cand_dir = self.retrieval_base_dir / candidate_id
        cand_dir.mkdir(parents=True, exist_ok=True)

        manifest.decision = decision
        manifest.decision_rationale = decision_rationale

        # Save retrieval_trace.jsonl
        collector = RetrievalTraceCollector(candidate_id=candidate_id)
        for ev in events:
            collector.record_event(ev)
        trace_path = cand_dir / "retrieval_trace.jsonl"
        collector.save_jsonl(trace_path)
        manifest.artifact_hashes["retrieval_trace.jsonl"] = _compute_sha256(trace_path.read_bytes())

        diagnostics = collector.compute_diagnostics()

        # Compute paired comparison
        paired_outcomes: List[RetrievalTaskPairOutcome] = []
        if baseline_records and candidate_records:
            paired_outcomes = compute_retrieval_paired_comparison(
                baseline_records=baseline_records,
                candidate_records=candidate_records,
                baseline_events=baseline_events,
                candidate_events=events,
            )
            save_paired_results_jsonl(paired_outcomes, cand_dir / "paired_results.jsonl")
            save_paired_results_csv(paired_outcomes, cand_dir / "paired_results.csv")
            manifest.artifact_hashes["paired_results.jsonl"] = _compute_sha256(
                (cand_dir / "paired_results.jsonl").read_bytes()
            )
            manifest.artifact_hashes["paired_results.csv"] = _compute_sha256(
                (cand_dir / "paired_results.csv").read_bytes()
            )

        # Compute quality and cost metrics
        cand_records = candidate_records or []
        target_mode = manifest.target_failure_mode
        quality = compute_retrieval_quality_metrics(
            candidate_records=cand_records,
            target_failure_mode=target_mode,
            paired_outcomes=paired_outcomes,
        )
        cost = compute_retrieval_cost_metrics(
            events=events,
            total_agent_tool_calls=total_agent_tool_calls,
            total_runtime_ms=total_runtime_ms,
            turns=turns,
        )

        # Save metrics.json
        met_path = cand_dir / "metrics.json"
        with open(met_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(
                {
                    "quality": quality.to_dict(),
                    "cost": cost.to_dict(),
                    "diagnostics": diagnostics.to_dict(),
                },
                f,
                indent=2,
                sort_keys=True,
            )
            f.write("\n")
        manifest.artifact_hashes["metrics.json"] = _compute_sha256(met_path.read_bytes())

        # Generate report.md
        report_text = generate_retrieval_experiment_report(
            manifest=manifest,
            diff=diff,
            quality=quality,
            cost=cost,
            diagnostics=diagnostics,
            paired_outcomes=paired_outcomes,
            smoke_passed=smoke_passed,
            validation_passed=validation_passed,
            held_out_passed=held_out_passed,
        )
        rep_path = cand_dir / "report.md"
        with open(rep_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(report_text)
        manifest.artifact_hashes["report.md"] = _compute_sha256(rep_path.read_bytes())

        # Final manifest write
        man_path = cand_dir / "manifest.json"
        with open(man_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        return cand_dir
