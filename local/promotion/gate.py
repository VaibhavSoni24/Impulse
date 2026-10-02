"""Deterministic Promotion Gate implementation for Stage 44.

Enforces:
- 5-dimensional evaluation: validation, held-out, runtime, config, reproducibility
- Non-collapsing decision logic: PROMOTE, REJECT, BLOCKED
- Fail-closed promotion action with zero bypass tolerance
- Current-best pointer consistency validation
- Full recording to experiments/candidates/promotions/ and history.jsonl
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.evaluation.db import DEFAULT_DB_PATH
from local.promotion.comparison import (
    compare_held_out,
    compare_validation,
    resolve_primary_metric,
)
from local.promotion.config import evaluate_configuration
from local.promotion.errors import (
    BaselineNotFoundError,
    CandidateNotFoundError,
    InvalidCurrentBestError,
    PromotionGateFailureError,
)
from local.promotion.evidence import (
    determine_runs_evidence_mode,
    fetch_candidate_runs,
)
from local.promotion.models import (
    CurrentBestValidationResult,
    EvidenceMode,
    GateDecision,
    GateDimensionStatus,
    PromotionEvaluationRecord,
)
from local.promotion.reproducibility import evaluate_reproducibility
from local.promotion.runtime import evaluate_runtime
from local.versioning.models import (
    CandidateManifest,
    CandidateStatus,
    LifecycleEvent,
    LifecycleEventType,
    PromotionStatus,
)
from local.versioning.registry import CandidateRegistry

PROMOTION_GATE_VERSION = "1.0.0"


class PromotionGate:
    """Deterministic, evidence-driven candidate promotion gate."""

    def __init__(
        self,
        candidates_dir: Optional[Path] = None,
        db_path: Path | str = DEFAULT_DB_PATH,
        repo_root: Optional[Path] = None,
    ) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent.parent
        self.candidates_dir = candidates_dir or (self.repo_root / "experiments" / "candidates")
        self.promotions_dir = self.candidates_dir / "promotions"
        self.promotions_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.registry = CandidateRegistry(candidates_dir=self.candidates_dir, repo_root=self.repo_root)

    def evaluate(
        self,
        candidate_id: str,
        baseline_id: Optional[str] = None,
    ) -> PromotionEvaluationRecord:
        """Evaluates all 5 promotion dimensions for candidate against baseline."""
        cand = self.registry.get_candidate(candidate_id)
        if cand is None:
            raise CandidateNotFoundError(f"Candidate '{candidate_id}' not found in registry.")

        # Resolve baseline
        baseline_cand: Optional[CandidateManifest] = None
        if baseline_id:
            baseline_cand = self.registry.get_candidate(baseline_id)
            if baseline_cand is None:
                raise BaselineNotFoundError(f"Specified baseline '{baseline_id}' not found in registry.")
        elif cand.parent_candidate_id:
            baseline_cand = self.registry.get_candidate(cand.parent_candidate_id)
            if baseline_cand is None:
                raise BaselineNotFoundError(
                    f"Parent baseline '{cand.parent_candidate_id}' for candidate '{candidate_id}' not found."
                )

        # Fetch runs
        cand_runs = fetch_candidate_runs(cand.candidate_id, self.db_path)
        base_runs = fetch_candidate_runs(baseline_cand.candidate_id, self.db_path) if baseline_cand else []

        # Determine evidence mode
        cand_ev_mode = determine_runs_evidence_mode(cand_runs, cand.evidence_mode)

        # 1. Validation improvement
        val_res = compare_validation(
            candidate_manifest=cand,
            candidate_runs=cand_runs,
            baseline_manifest=baseline_cand,
            baseline_runs=base_runs,
            evidence_mode=cand_ev_mode,
        )

        # 2. Held-out regression
        held_out_res = compare_held_out(
            candidate_manifest=cand,
            candidate_runs=cand_runs,
            baseline_manifest=baseline_cand,
            baseline_runs=base_runs,
            evidence_mode=cand_ev_mode,
        )

        # 3. Runtime acceptability
        rt_res = evaluate_runtime(
            candidate_manifest=cand,
            candidate_runs=cand_runs,
            evidence_mode=cand_ev_mode,
        )

        # 4. Configuration validity
        cfg_res = evaluate_configuration(
            candidate_manifest=cand,
            baseline_manifest=baseline_cand,
            repo_root=self.repo_root,
        )

        # 5. Reproducibility
        rep_res = evaluate_reproducibility(
            candidate_manifest=cand,
            candidate_runs=cand_runs,
            evidence_mode=cand_ev_mode,
        )

        # Collect dimension statuses & reasons
        dim_statuses = [
            val_res.dimension_status,
            held_out_res.dimension_status,
            rt_res.dimension_status,
            cfg_res.dimension_status,
            rep_res.dimension_status,
        ]

        reasons: List[str] = []
        if cfg_res.dimension_status != GateDimensionStatus.PASS.value:
            reasons.append(f"Configuration: {cfg_res.notes}")
        if val_res.dimension_status == GateDimensionStatus.FAIL.value:
            reasons.append(f"Validation: {val_res.notes}")
        elif val_res.dimension_status == GateDimensionStatus.UNKNOWN.value:
            reasons.append(f"Validation: {val_res.notes}")
        if held_out_res.dimension_status == GateDimensionStatus.FAIL.value:
            reasons.append(f"Held-Out: {held_out_res.notes}")
        elif held_out_res.dimension_status == GateDimensionStatus.UNKNOWN.value:
            reasons.append(f"Held-Out: {held_out_res.notes}")
        if rt_res.dimension_status == GateDimensionStatus.FAIL.value:
            reasons.append(f"Runtime: {rt_res.notes}")
        elif rt_res.dimension_status == GateDimensionStatus.UNKNOWN.value:
            reasons.append(f"Runtime: {rt_res.notes}")
        if rep_res.dimension_status == GateDimensionStatus.FAIL.value:
            reasons.append(f"Reproducibility: {rep_res.notes}")
        elif rep_res.dimension_status == GateDimensionStatus.UNKNOWN.value:
            reasons.append(f"Reproducibility: {rep_res.notes}")

        # Special Case: L1
        if cand.candidate_id == "L1":
            overall_decision = GateDecision.BLOCKED.value
            reasons = [
                "L1 adapter weights not trained; Stage 40 A/B unverified; zero measured adapter improvement."
            ]
        # Special Case: RC1
        elif cand.candidate_id == "RC1":
            overall_decision = GateDecision.BLOCKED.value
            reasons = [
                "NO_RELEASE_CANDIDATE_CONFIGURATION: RC1 is a reserved release-candidate identity pending Stage 50."
            ]
        # Special Case: M0-M5 structural vs scientific promotion
        elif cand.candidate_id in {"M0", "M1", "M2", "M3", "M4", "M5"} and cand_ev_mode != EvidenceMode.LIVE.value:
            overall_decision = GateDecision.BLOCKED.value
            reasons.insert(
                0,
                f"Candidate {cand.candidate_id} passed structural submission validation, "
                "but lacks live benchmark evaluation data required for scientific promotion.",
            )
        # General non-collapsing gate decision rules
        elif GateDimensionStatus.FAIL.value in dim_statuses:
            overall_decision = GateDecision.REJECT.value
        elif GateDimensionStatus.UNKNOWN.value in dim_statuses:
            overall_decision = GateDecision.BLOCKED.value
        else:
            overall_decision = GateDecision.PROMOTE.value
            reasons.append("All required promotion gate dimensions successfully verified.")

        now_str = datetime.now(timezone.utc).isoformat()
        primary_metric_name, _ = resolve_primary_metric(cand)

        source_manifests: Dict[str, str] = {
            cand.candidate_id: cand.manifest_hash or "",
        }
        if baseline_cand:
            source_manifests[baseline_cand.candidate_id] = baseline_cand.manifest_hash or ""

        record = PromotionEvaluationRecord(
            candidate_id=cand.candidate_id,
            baseline_candidate_id=baseline_cand.candidate_id if baseline_cand else None,
            decision=overall_decision,
            timestamp=now_str,
            gate_version=PROMOTION_GATE_VERSION,
            primary_metric=primary_metric_name,
            validation_result=val_res.to_dict(),
            held_out_result=held_out_res.to_dict(),
            runtime_result=rt_res.to_dict(),
            configuration_result=cfg_res.to_dict(),
            reproducibility_result=rep_res.to_dict(),
            overall_result=overall_decision,
            evidence_mode=cand_ev_mode,
            reasons=reasons,
            source_manifests=source_manifests,
            source_hashes={
                "candidate_manifest": cand.manifest_hash or "",
                "root_prompt": cand.root_prompt_hash,
                "benchmark_manifest": cand.benchmark_manifest_hash,
            },
        )
        return record

    def save_promotion_record(
        self,
        record: PromotionEvaluationRecord,
        candidate_manifest: CandidateManifest,
        baseline_manifest: Optional[CandidateManifest] = None,
        record_event: bool = True,
    ) -> Path:
        """Saves machine-readable promotion JSON and human-readable Markdown report."""
        json_path = self.promotions_dir / f"{record.candidate_id}.json"
        json_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

        # Import markdown generator lazily to prevent circular imports
        from local.promotion.reporting import generate_promotion_markdown_report

        md_content = generate_promotion_markdown_report(
            record=record,
            candidate_manifest=candidate_manifest,
            baseline_manifest=baseline_manifest,
        )
        md_path = self.promotions_dir / f"{record.candidate_id}.md"
        md_path.write_text(md_content, encoding="utf-8")

        if record_event:
            self.registry.record_event(
                LifecycleEvent(
                    candidate_id=record.candidate_id,
                    event_type="PROMOTION_EVALUATED",
                    timestamp=record.timestamp,
                    git_commit=candidate_manifest.git_commit,
                    actor="IMPULSE-Gate",
                    reason=f"Gate evaluated decision: {record.decision}",
                    source_manifest_hash=candidate_manifest.manifest_hash or "",
                    notes=f"Gate version {record.gate_version}",
                )
            )

        return json_path

    def promote_candidate(
        self,
        candidate_id: str,
        baseline_id: Optional[str] = None,
        actor: str = "IMPULSE-Gate",
        notes: str = "",
        save_record: bool = True,
    ) -> PromotionEvaluationRecord:
        """Promotes a candidate strictly if the gate returns PROMOTE."""
        record = self.evaluate(candidate_id, baseline_id)
        if record.decision != GateDecision.PROMOTE.value:
            raise PromotionGateFailureError(
                f"Candidate '{candidate_id}' cannot be promoted. Gate decision: {record.decision}. "
                f"Reasons: {record.reasons}"
            )

        cand = self.registry.get_candidate(candidate_id)
        base = self.registry.get_candidate(baseline_id or cand.parent_candidate_id) if (baseline_id or cand.parent_candidate_id) else None

        if save_record and cand:
            self.save_promotion_record(record, cand, base, record_event=False)

            # Update candidate status
            cand_dir = self.candidates_dir / candidate_id
            manifest_file = cand_dir / "manifest.json"
            if manifest_file.is_file():
                m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                m_data["status"] = CandidateStatus.PROMOTED.value
                m_data["promotion_status"] = PromotionStatus.PROMOTED.value
                manifest_file.write_text(json.dumps(m_data, indent=2), encoding="utf-8")

            # Update registry.json
            reg = self.registry.load_registry()
            if candidate_id in reg.get("candidates", {}):
                reg["candidates"][candidate_id]["status"] = CandidateStatus.PROMOTED.value
                self.registry.registry_file.write_text(json.dumps(reg, indent=2), encoding="utf-8")

            # Record lifecycle events
            now = datetime.now(timezone.utc).isoformat()
            self.registry.record_event(
                LifecycleEvent(
                    candidate_id=candidate_id,
                    event_type="PROMOTION_EVALUATED",
                    timestamp=now,
                    git_commit=cand.git_commit,
                    actor=actor,
                    reason=f"Gate evaluated: {record.decision}",
                    source_manifest_hash=cand.manifest_hash or "",
                    notes=notes or "Gate evaluation completed",
                )
            )
            self.registry.record_event(
                LifecycleEvent(
                    candidate_id=candidate_id,
                    event_type=LifecycleEventType.PROMOTED.value,
                    timestamp=now,
                    git_commit=cand.git_commit,
                    actor=actor,
                    reason="Satisfied all 5 promotion gate dimensions",
                    source_manifest_hash=cand.manifest_hash or "",
                    notes=notes or f"Promoted candidate {candidate_id}",
                )
            )

        return record

    def reject_candidate(
        self,
        candidate_id: str,
        baseline_id: Optional[str] = None,
        actor: str = "IMPULSE-Gate",
        reason: str = "",
        save_record: bool = True,
    ) -> PromotionEvaluationRecord:
        """Rejects a candidate and preserves evaluation records for learning."""
        record = self.evaluate(candidate_id, baseline_id)
        # Even if evaluate returned BLOCKED, an explicit reject enforces REJECT
        record.decision = GateDecision.REJECT.value
        record.overall_result = GateDecision.REJECT.value
        if reason:
            record.reasons.insert(0, reason)

        cand = self.registry.get_candidate(candidate_id)
        base = self.registry.get_candidate(baseline_id or cand.parent_candidate_id) if (baseline_id or cand.parent_candidate_id) else None

        if save_record and cand:
            self.save_promotion_record(record, cand, base, record_event=False)

            # Update candidate status
            cand_dir = self.candidates_dir / candidate_id
            manifest_file = cand_dir / "manifest.json"
            if manifest_file.is_file():
                m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                m_data["status"] = CandidateStatus.REJECTED.value
                m_data["promotion_status"] = PromotionStatus.REJECTED.value
                manifest_file.write_text(json.dumps(m_data, indent=2), encoding="utf-8")

            # Update registry.json
            reg = self.registry.load_registry()
            if candidate_id in reg.get("candidates", {}):
                reg["candidates"][candidate_id]["status"] = CandidateStatus.REJECTED.value
                self.registry.registry_file.write_text(json.dumps(reg, indent=2), encoding="utf-8")

            # Record event
            now = datetime.now(timezone.utc).isoformat()
            self.registry.record_event(
                LifecycleEvent(
                    candidate_id=candidate_id,
                    event_type=LifecycleEventType.REJECTED.value,
                    timestamp=now,
                    git_commit=cand.git_commit,
                    actor=actor,
                    reason=reason or f"Rejected by gate: {record.reasons}",
                    source_manifest_hash=cand.manifest_hash or "",
                    notes=f"Candidate {candidate_id} rejected",
                )
            )

        return record

    def validate_current_best(self) -> CurrentBestValidationResult:
        """Validates consistency and integrity of current_best.json."""
        pointer = self.registry.get_current_best()
        if pointer is None:
            return CurrentBestValidationResult(
                valid=False,
                current_best_candidate_id="NONE",
                candidate_status="MISSING",
                manifest_verified=False,
                evidence_mode=EvidenceMode.UNAVAILABLE.value,
                issues=["current_best.json does not exist"],
            )

        cand = self.registry.get_candidate(pointer.candidate_id)
        issues: List[str] = []

        if cand is None:
            issues.append(f"Current best candidate '{pointer.candidate_id}' is not registered in registry")
            return CurrentBestValidationResult(
                valid=False,
                current_best_candidate_id=pointer.candidate_id,
                candidate_status="NOT_REGISTERED",
                manifest_verified=False,
                evidence_mode=EvidenceMode.UNAVAILABLE.value,
                issues=issues,
            )

        # Check manifest hash matches pointer
        if cand.manifest_hash != pointer.manifest_hash:
            issues.append(
                f"Manifest hash mismatch: pointer has '{pointer.manifest_hash}', candidate has '{cand.manifest_hash}'"
            )

        # Check candidate status
        if cand.status == CandidateStatus.REJECTED.value:
            issues.append(f"Current best candidate '{pointer.candidate_id}' is marked REJECTED")

        allowed_statuses = {
            CandidateStatus.VALIDATED.value,
            CandidateStatus.PROMOTED.value,
            CandidateStatus.SMOKE_PASSED.value,
            CandidateStatus.HELD_OUT_CONFIRMED.value,
        }
        if cand.status not in allowed_statuses:
            issues.append(
                f"Current best status '{cand.status}' invalid. Allowed: {sorted(allowed_statuses)}"
            )

        is_valid = len(issues) == 0
        return CurrentBestValidationResult(
            valid=is_valid,
            current_best_candidate_id=pointer.candidate_id,
            candidate_status=cand.status,
            manifest_verified=cand.manifest_hash == pointer.manifest_hash,
            evidence_mode=cand.evidence_mode,
            issues=issues,
        )

    def explain_promotion(self, candidate_id: str) -> str:
        """Generates formatted explanation of candidate evaluation."""
        rec = self.evaluate(candidate_id)
        lines = [
            f"=== Promotion Evaluation: {candidate_id} ===",
            f"Gate Version:      {rec.gate_version}",
            f"Decision:          {rec.decision}",
            f"Baseline:          {rec.baseline_candidate_id or 'None (Root Baseline)'}",
            f"Primary Metric:    {rec.primary_metric}",
            f"Evidence Mode:     {rec.evidence_mode}",
            "",
            "Dimension Breakdown:",
            f"  1. Validation:      {rec.validation_result.get('dimension_status')} ({rec.validation_result.get('notes')})",
            f"  2. Held-Out:        {rec.held_out_result.get('dimension_status')} ({rec.held_out_result.get('notes')})",
            f"  3. Runtime:         {rec.runtime_result.get('dimension_status')} ({rec.runtime_result.get('notes')})",
            f"  4. Configuration:   {rec.configuration_result.get('dimension_status')} ({rec.configuration_result.get('notes')})",
            f"  5. Reproducibility: {rec.reproducibility_result.get('dimension_status')} ({rec.reproducibility_result.get('notes')})",
            "",
            "Reasons:",
        ]
        for r in rec.reasons:
            lines.append(f"  - {r}")
        return "\n".join(lines)
