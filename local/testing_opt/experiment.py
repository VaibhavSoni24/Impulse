"""Testing Strategy Experiment Orchestration and Execution Engine (Stage 34 Sections 5, 33).

Integrates:
- Baseline T0 establishment
- T1..T3 candidate creation and single-dimension validation
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
from local.testing_opt.diff import (
    TestPolicyDiff,
    compute_test_policy_diff,
    render_test_policy_diff_md,
)
from local.testing_opt.metrics import (
    compute_test_cost_metrics,
    compute_test_evidence_metrics,
)
from local.testing_opt.models import (
    TestCandidateManifest,
    TestCostMetrics,
    TestDiagnostics,
    TestEvidenceMetrics,
    TestExecutionEvent,
    TestHypothesis,
    TestPolicy,
    TestTaskPairOutcome,
    TestingStrategyVariant,
)
from local.testing_opt.paired import (
    compute_test_paired_comparison,
    save_test_paired_results_csv,
    save_test_paired_results_jsonl,
)
from local.testing_opt.policy import build_t0_targeted_policy, get_canonical_testing_policy
from local.testing_opt.reporting import generate_testing_experiment_report
from local.testing_opt.trace import TestTraceCollector
from local.testing_opt.validator import (
    EXPECTED_FROZEN_TEST_SKILL_SHA256,
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_RETRIEVAL_R0_POLICY_SHA256,
    EXPECTED_TOPOLOGY_ID,
    TestingValidationError,
    validate_testing_candidate_integrity,
)


def _compute_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class TestingExperimentManager:
    """Manages candidate creation, diffing, execution, and artifact auditing for testing strategy experiments."""

    def __init__(
        self,
        testing_base_dir: Path | str = Path("experiments/testing"),
        repo_root: Optional[Path | str] = None,
        benchmark_split: str = "validation",
    ) -> None:
        self.testing_base_dir = Path(testing_base_dir)
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.benchmark_split = benchmark_split

    def ensure_t0_baseline(
        self,
        git_commit: str = "",
        evidence_mode: str = "UNAVAILABLE",
    ) -> TestCandidateManifest:
        """Ensures that the immutable T0 baseline exists under experiments/testing/T0/."""
        t0_dir = self.testing_base_dir / "T0"
        t0_manifest_path = t0_dir / "manifest.json"
        if t0_manifest_path.is_file():
            with open(t0_manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TestCandidateManifest.from_dict(data)

        t0_dir.mkdir(parents=True, exist_ok=True)
        policy = build_t0_targeted_policy()
        pol_hash = policy.compute_policy_hash()

        # Save policy.json
        pol_path = t0_dir / "policy.json"
        with open(pol_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(policy.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        # Save empty baseline trace
        trace_path = t0_dir / "test_trace.jsonl"
        with open(trace_path, "w", encoding="utf-8", newline="\n") as f:
            pass

        manifest = TestCandidateManifest(
            candidate_id="T0",
            parent_candidate_id=None,
            strategy_variant=TestingStrategyVariant.T0.value,
            test_policy_hash=pol_hash,
            target_failure_mode="BASELINE",
            benchmark_split=self.benchmark_split,
            evidence_mode=evidence_mode,
            model_id=EXPECTED_MODEL_ID,
            topology_id=EXPECTED_TOPOLOGY_ID,
            prompt_id="P0",
            prompt_sha256=EXPECTED_P0_PROMPT_SHA256,
            retrieval_id="R0",
            retrieval_policy_hash=EXPECTED_RETRIEVAL_R0_POLICY_SHA256,
            frozen_test_skill_sha256=EXPECTED_FROZEN_TEST_SKILL_SHA256,
            created_from_commit=git_commit,
            experiment_id="exp-testing-t0-baseline",
            decision="PROMOTED",
            decision_rationale="Immutable baseline T0 established (minimal targeted test execution).",
            artifact_hashes={
                "policy.json": _compute_sha256(pol_path.read_bytes()),
                "test_trace.jsonl": _compute_sha256(trace_path.read_bytes()),
            },
        )

        quality = TestEvidenceMetrics(
            pass_rate=0.0,
            failure_rate=1.0 if evidence_mode != "UNAVAILABLE" else 0.0,
            targeted_failure_mode="BASELINE",
            targeted_failure_count=0,
            targeted_failure_rate=0.0,
        )
        cost = TestCostMetrics(
            total_test_commands=0,
            targeted_commands=0,
            adjacent_commands=0,
            subsystem_commands=0,
            full_suite_commands=0,
            total_tests_executed=0,
            total_test_duration_ms=0.0,
            mean_test_duration_ms=None,
            median_test_duration_ms=None,
            p95_test_duration_ms=None,
            total_output_bytes=0,
            repeated_command_count=0,
            duplicate_test_case_count=0,
            total_agent_runtime_ms=None,
            testing_tool_call_share=0.0,
        )

        # Save metrics.json
        met_path = t0_dir / "metrics.json"
        with open(met_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"quality": quality.to_dict(), "cost": cost.to_dict()}, f, indent=2, sort_keys=True)
            f.write("\n")
        manifest.artifact_hashes["metrics.json"] = _compute_sha256(met_path.read_bytes())

        # Generate report.md
        diff = compute_test_policy_diff(policy, policy)
        report_text = generate_testing_experiment_report(
            manifest=manifest,
            diff=diff,
            quality=quality,
            cost=cost,
            diagnostics=TestDiagnostics(),
            paired_outcomes=[],
            validation_passed=True,
        )
        rep_path = t0_dir / "report.md"
        with open(rep_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(report_text)
        manifest.artifact_hashes["report.md"] = _compute_sha256(rep_path.read_bytes())

        # Save final manifest
        with open(t0_manifest_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        return manifest

    def create_candidate(
        self,
        candidate_id: str,
        parent_candidate_id: str,
        policy: TestPolicy,
        hypothesis: Optional[TestHypothesis],
        source_failure_cluster_id: Optional[str] = None,
        git_commit: str = "",
        evidence_mode: str = "UNAVAILABLE",
    ) -> Tuple[TestCandidateManifest, TestPolicyDiff]:
        """Creates and validates an isolated testing strategy candidate T(n)."""
        cand_dir = self.testing_base_dir / candidate_id
        if cand_dir.exists():
            raise FileExistsError(f"Testing candidate {candidate_id} already exists at {cand_dir}")

        # Ensure parent exists
        parent_dir = self.testing_base_dir / parent_candidate_id
        if parent_candidate_id == "T0" and not parent_dir.exists():
            self.ensure_t0_baseline(git_commit=git_commit, evidence_mode=evidence_mode)

        parent_policy_file = parent_dir / "policy.json"
        if not parent_policy_file.is_file():
            raise FileNotFoundError(f"Parent policy file not found: {parent_policy_file}")

        with open(parent_policy_file, "r", encoding="utf-8") as f:
            parent_policy = TestPolicy.from_dict(json.load(f))

        diff = compute_test_policy_diff(parent_policy, policy)

        policy_hash = policy.compute_policy_hash()
        manifest = TestCandidateManifest(
            candidate_id=candidate_id,
            parent_candidate_id=parent_candidate_id,
            strategy_variant=policy.strategy_id,
            test_policy_hash=policy_hash,
            source_failure_cluster_id=source_failure_cluster_id,
            target_failure_mode=hypothesis.target_failure if hypothesis else "UNKNOWN",
            hypothesis=hypothesis,
            benchmark_split=self.benchmark_split,
            evidence_mode=evidence_mode,
            model_id=EXPECTED_MODEL_ID,
            topology_id=EXPECTED_TOPOLOGY_ID,
            prompt_id="P0",
            prompt_sha256=EXPECTED_P0_PROMPT_SHA256,
            retrieval_id="R0",
            retrieval_policy_hash=EXPECTED_RETRIEVAL_R0_POLICY_SHA256,
            frozen_test_skill_sha256=EXPECTED_FROZEN_TEST_SKILL_SHA256,
            created_from_commit=git_commit,
            experiment_id=f"exp-testing-{candidate_id.lower()}",
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
        is_valid, errors = validate_testing_candidate_integrity(
            manifest=manifest,
            policy=policy,
            repo_root=self.repo_root,
        )
        if not is_valid:
            import shutil
            shutil.rmtree(cand_dir, ignore_errors=True)
            raise TestingValidationError(f"Testing candidate validation failed: {'; '.join(errors)}")

        # Write policy_diff.json and policy_diff.md
        diff_json_path = cand_dir / "policy_diff.json"
        with open(diff_json_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(diff.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")
        manifest.artifact_hashes["policy_diff.json"] = _compute_sha256(diff_json_path.read_bytes())

        diff_md_path = cand_dir / "policy_diff.md"
        with open(diff_md_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_test_policy_diff_md(diff))
        manifest.artifact_hashes["policy_diff.md"] = _compute_sha256(diff_md_path.read_bytes())

        # Save initial manifest
        man_path = cand_dir / "manifest.json"
        with open(man_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        return manifest, diff

    def record_experiment_results(
        self,
        candidate_id: str,
        manifest: TestCandidateManifest,
        policy: TestPolicy,
        diff: TestPolicyDiff,
        events: List[TestExecutionEvent],
        baseline_records: Optional[List[FailureRecord]] = None,
        candidate_records: Optional[List[FailureRecord]] = None,
        baseline_events: Optional[List[TestExecutionEvent]] = None,
        smoke_passed: Optional[bool] = None,
        validation_passed: Optional[bool] = None,
        held_out_passed: Optional[bool] = None,
        decision: str = "INCONCLUSIVE",
        decision_rationale: str = "",
        total_agent_tool_calls: Optional[int] = None,
        total_runtime_ms: Optional[float] = None,
    ) -> Path:
        """Records complete experiment artifacts, metrics, paired comparisons, and audit report."""
        cand_dir = self.testing_base_dir / candidate_id
        cand_dir.mkdir(parents=True, exist_ok=True)

        manifest.decision = decision
        manifest.decision_rationale = decision_rationale

        # Save test_trace.jsonl
        collector = TestTraceCollector(candidate_id=candidate_id)
        for ev in events:
            collector.record_event(ev)
        trace_path = cand_dir / "test_trace.jsonl"
        collector.save_jsonl(trace_path)
        manifest.artifact_hashes["test_trace.jsonl"] = _compute_sha256(trace_path.read_bytes())

        diagnostics = collector.compute_diagnostics()

        # Compute paired comparison
        paired_outcomes: List[TestTaskPairOutcome] = []
        if baseline_records and candidate_records:
            paired_outcomes = compute_test_paired_comparison(
                baseline_records=baseline_records,
                candidate_records=candidate_records,
                baseline_events=baseline_events,
                candidate_events=events,
            )
            save_test_paired_results_jsonl(paired_outcomes, cand_dir / "paired_results.jsonl")
            save_test_paired_results_csv(paired_outcomes, cand_dir / "paired_results.csv")
            manifest.artifact_hashes["paired_results.jsonl"] = _compute_sha256(
                (cand_dir / "paired_results.jsonl").read_bytes()
            )
            manifest.artifact_hashes["paired_results.csv"] = _compute_sha256(
                (cand_dir / "paired_results.csv").read_bytes()
            )

        # Compute quality and cost metrics
        cand_records = candidate_records or []
        target_mode = manifest.target_failure_mode
        quality = compute_test_evidence_metrics(
            events=events,
            candidate_records=cand_records,
            target_failure_mode=target_mode,
            paired_outcomes=paired_outcomes,
        )
        cost = compute_test_cost_metrics(
            events=events,
            total_agent_tool_calls=total_agent_tool_calls,
            total_agent_runtime_ms=total_runtime_ms,
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
        report_text = generate_testing_experiment_report(
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
