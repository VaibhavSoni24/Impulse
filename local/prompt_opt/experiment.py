"""Prompt Experiment Orchestration and Execution (Stage 32 Sections 10, 19, 20).

Integrates prompt candidate generation, validation, FDD evaluation rounds,
task-level paired comparison, and artifact persistence under experiments/prompts/<candidate>/.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.fdd.evaluator import FDDEvaluator
from local.fdd.loop import FDDLoop
from local.fdd.models import (
    FDDRunDelta,
    FailureRecord,
    Intervention,
    InterventionScope,
    PromotionDecision,
)
from local.prompt_opt.baseline import (
    DEFAULT_SOURCE_PROMPT,
    establish_p0_baseline,
)
from local.prompt_opt.diff import (
    compute_prompt_diff,
    detect_prompt_bloat,
    render_prompt_diff_md,
)
from local.prompt_opt.models import (
    PromptBloatReport,
    PromptCandidateManifest,
    PromptDiff,
    PromptHypothesis,
    TaskPairOutcome,
)
from local.prompt_opt.paired import (
    compute_task_paired_comparison,
    save_paired_results_csv,
    save_paired_results_jsonl,
)
from local.prompt_opt.reporting import generate_prompt_experiment_report
from local.prompt_opt.validator import (
    PromptValidationError,
    validate_prompt_candidate_integrity,
)


def _compute_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class PromptExperimentManager:
    """Manages prompt candidate creation, diffing, and execution over FDD."""

    def __init__(
        self,
        prompts_base_dir: Path | str = Path("experiments/prompts"),
        repo_root: Optional[Path | str] = None,
        benchmark_split: str = "validation",
        split_version: str = "v1",
    ) -> None:
        self.prompts_base_dir = Path(prompts_base_dir)
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.benchmark_split = benchmark_split
        self.split_version = split_version

    def ensure_p0_baseline(self, git_commit: str = "") -> PromptCandidateManifest:
        """Ensures that the immutable P0 baseline exists in experiments/prompts/P0/."""
        p0_dir = self.prompts_base_dir / "P0"
        p0_manifest_path = p0_dir / "manifest.json"
        if p0_manifest_path.is_file():
            with open(p0_manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PromptCandidateManifest.from_dict(data)

        return establish_p0_baseline(
            output_dir=p0_dir,
            git_commit=git_commit,
        )

    def create_candidate(
        self,
        candidate_id: str,
        parent_candidate_id: str,
        new_prompt_content: str,
        hypothesis: PromptHypothesis,
        source_failure_cluster_id: Optional[str] = None,
        git_commit: str = "",
        evidence_mode: str = "UNAVAILABLE",
    ) -> Tuple[PromptCandidateManifest, PromptDiff, PromptBloatReport]:
        """Creates and validates an isolated prompt candidate P(n)."""
        cand_dir = self.prompts_base_dir / candidate_id
        if cand_dir.exists():
            raise FileExistsError(f"Prompt candidate {candidate_id} already exists at {cand_dir}")

        # Ensure parent exists
        parent_dir = self.prompts_base_dir / parent_candidate_id
        if parent_candidate_id == "P0" and not parent_dir.exists():
            self.ensure_p0_baseline(git_commit=git_commit)

        parent_prompt_file = parent_dir / "root.md"
        if not parent_prompt_file.is_file():
            raise FileNotFoundError(f"Parent prompt file not found: {parent_prompt_file}")

        parent_bytes = parent_prompt_file.read_bytes()
        parent_content = parent_bytes.decode("utf-8")
        parent_hash = _compute_sha256(parent_bytes)

        # Write candidate prompt to temp location for validation
        cand_dir.mkdir(parents=True, exist_ok=True)
        cand_prompt_file = cand_dir / "root.md"
        with open(cand_prompt_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_prompt_content)
        cand_hash = _compute_sha256(cand_prompt_file.read_bytes())

        # Compute diff and bloat diagnostics
        diff = compute_prompt_diff(
            parent_id=parent_candidate_id,
            candidate_id=candidate_id,
            parent_content=parent_content,
            candidate_content=new_prompt_content,
        )
        bloat = detect_prompt_bloat(new_prompt_content)

        manifest = PromptCandidateManifest(
            candidate_id=candidate_id,
            parent_candidate_id=parent_candidate_id,
            prompt_id=f"{candidate_id}_root",
            prompt_path=str(cand_prompt_file).replace("\\", "/"),
            prompt_sha256=cand_hash,
            parent_prompt_sha256=parent_hash,
            source_failure_cluster_id=source_failure_cluster_id,
            target_failure_mode=hypothesis.target_failure,
            hypothesis=hypothesis,
            intervention_type=hypothesis.change_type,
            changed_section=hypothesis.changed_section or "Operational Workflow",
            changed_files=["root.md"],
            benchmark_split=self.benchmark_split,
            evidence_mode=evidence_mode,
            created_from_commit=git_commit,
            experiment_id=f"exp-prompt-{candidate_id.lower()}",
            decision="PROPOSED",
        )

        # Validate candidate
        is_valid, errors = validate_prompt_candidate_integrity(
            manifest=manifest,
            candidate_prompt_path=cand_prompt_file,
            parent_prompt_path=parent_prompt_file,
            repo_root=self.repo_root,
        )
        if not is_valid:
            # Clean up candidate dir on validation failure
            import shutil
            shutil.rmtree(cand_dir, ignore_errors=True)
            raise PromptValidationError(f"Prompt candidate validation failed: {'; '.join(errors)}")

        # Save diff artifacts
        diff_json_path = cand_dir / "prompt_diff.json"
        with open(diff_json_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(diff.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")
        manifest.artifact_hashes["prompt_diff.json"] = _compute_sha256(diff_json_path.read_bytes())

        diff_md_path = cand_dir / "prompt_diff.md"
        diff_md_text = render_prompt_diff_md(diff)
        with open(diff_md_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(diff_md_text)
        manifest.artifact_hashes["prompt_diff.md"] = _compute_sha256(diff_md_path.read_bytes())

        manifest.artifact_hashes["root.md"] = cand_hash

        # Initial manifest save
        man_path = cand_dir / "manifest.json"
        with open(man_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        return manifest, diff, bloat

    def record_experiment_results(
        self,
        candidate_id: str,
        manifest: PromptCandidateManifest,
        diff: PromptDiff,
        delta: Optional[FDDRunDelta] = None,
        decision: str = "INCONCLUSIVE",
        decision_rationale: str = "",
        smoke_passed: Optional[bool] = None,
        validation_passed: Optional[bool] = None,
        held_out_passed: Optional[bool] = None,
        baseline_records: Optional[List[FailureRecord]] = None,
        candidate_records: Optional[List[FailureRecord]] = None,
        bloat_report: Optional[PromptBloatReport] = None,
    ) -> Path:
        """Records complete experiment results, paired outcomes, and audit report."""
        cand_dir = self.prompts_base_dir / candidate_id
        cand_dir.mkdir(parents=True, exist_ok=True)

        manifest.decision = decision
        manifest.decision_rationale = decision_rationale

        # Task-level paired comparison
        paired_outcomes: List[TaskPairOutcome] = []
        if baseline_records and candidate_records:
            paired_outcomes = compute_task_paired_comparison(baseline_records, candidate_records)
            save_paired_results_jsonl(paired_outcomes, cand_dir / "paired_results.jsonl")
            save_paired_results_csv(paired_outcomes, cand_dir / "paired_results.csv")
            manifest.artifact_hashes["paired_results.jsonl"] = _compute_sha256(
                (cand_dir / "paired_results.jsonl").read_bytes()
            )
            manifest.artifact_hashes["paired_results.csv"] = _compute_sha256(
                (cand_dir / "paired_results.csv").read_bytes()
            )

        # Generate report.md
        report_text = generate_prompt_experiment_report(
            manifest=manifest,
            diff=diff,
            delta=delta,
            paired_outcomes=paired_outcomes,
            smoke_passed=smoke_passed,
            validation_passed=validation_passed,
            held_out_passed=held_out_passed,
            bloat_report=bloat_report,
        )
        report_path = cand_dir / "report.md"
        with open(report_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(report_text)
        manifest.artifact_hashes["report.md"] = _compute_sha256(report_path.read_bytes())

        # Final manifest save
        man_path = cand_dir / "manifest.json"
        with open(man_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

        return cand_dir
