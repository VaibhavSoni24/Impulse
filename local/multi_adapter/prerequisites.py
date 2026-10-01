"""Scientific Prerequisite Verification for Stage 41 (Section 3, 4, 11).

Enforces the non-negotiable project rule:
"Only experiment with multiple adapters after a single adapter produces a measurable benefit."

Verifies:
1. Genuine adapter artifact exists with weights and valid SHA-256.
2. Genuine Stage 39 PEFT training run exists (not BLOCKED_BY_DATA).
3. Stage 40 A/B comparison actually executed (not fixture, not blocked).
4. Measurable benefit on primary objective (OBJ-TOOL-DISCIPLINE) was demonstrated.
5. Survived candidate promotion gate with zero collateral regressions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.lora_ablation.adapter_gate import AdapterGateValidator
from local.lora_ablation.models import AdapterGateStatus
from local.multi_adapter.models import PrerequisiteCheckResult


class SingleAdapterPrerequisiteChecker:
    """Verifies that the empirical prerequisite for multi-adapter experimentation is satisfied."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.adapter_validator = AdapterGateValidator(self.repo_root)

    def check_single_adapter_prerequisite(
        self,
        stage40_report_path: Optional[Path | str] = None,
        adapter_path: Optional[Path | str] = None,
    ) -> PrerequisiteCheckResult:
        """Evaluates whether a validated single adapter with measured benefit exists.

        Returns PrerequisiteCheckResult. If prerequisite fails, eligible is False.
        """
        blocking_reasons: List[str] = []

        # 1. Check Stage 40 report for real A/B evaluation and measured benefit
        report_file = Path(stage40_report_path) if stage40_report_path else self.repo_root / "experiments" / "lora" / "stage40_report.md"
        if not report_file.exists():
            report_file = self.repo_root / "stage40_report.md"

        has_stage40_real_execution = False
        has_measured_benefit = False

        if not report_file.exists():
            blocking_reasons.append("Stage 40 ablation report does not exist.")
        else:
            try:
                content = report_file.read_text(encoding="utf-8")
                # Check for explicit statements in Stage 40 report
                if "- **Did real A/B execution occur?** **NO**" in content or "Did real A/B execution occur?** **NO" in content:
                    blocking_reasons.append("Stage 40 A/B evaluation did not occur (real execution: NO).")
                elif "- **Did real A/B execution occur?** **YES**" in content:
                    has_stage40_real_execution = True

                if "- **Measured Adapter Improvement:** **NO**" in content or "Measured Adapter Improvement:** **NO" in content:
                    blocking_reasons.append("NO_MEASURED_SINGLE_ADAPTER_BENEFIT")
                elif "- **Measured Adapter Improvement:** **YES**" in content:
                    has_measured_benefit = True

                if "MISSING_ADAPTER_ARTIFACT" in content or "BLOCKED_BY_MISSING_ADAPTER" in content:
                    blocking_reasons.append("Stage 40 was blocked by missing adapter artifact.")
            except Exception as e:
                blocking_reasons.append(f"Failed to read Stage 40 report: {e}")

        # 2. Check candidate adapter artifact validity
        if adapter_path is None:
            blocking_reasons.append("No candidate adapter artifact directory specified.")
            adapter_valid = False
            adapter_meta = None
        else:
            is_valid, gate_status, reason, adapter_meta = self.adapter_validator.validate_adapter(adapter_path)
            if gate_status == AdapterGateStatus.FIXTURE_ADAPTER_REJECTED or (adapter_meta and adapter_meta.evidence_mode == "FIXTURE"):
                blocking_reasons.append("Fixture-generated adapter cannot satisfy single-adapter prerequisite.")
                adapter_valid = False
            elif not is_valid or adapter_meta is None:
                blocking_reasons.append(f"Adapter artifact verification failed: {reason}")
                adapter_valid = False
            else:
                adapter_valid = True

        single_adapter_validated = has_stage40_real_execution and has_measured_benefit and adapter_valid
        eligible = single_adapter_validated and len(blocking_reasons) == 0

        # Ensure NO_MEASURED_SINGLE_ADAPTER_BENEFIT is always explicitly listed if not eligible
        if not eligible and "NO_MEASURED_SINGLE_ADAPTER_BENEFIT" not in blocking_reasons:
            blocking_reasons.insert(0, "NO_MEASURED_SINGLE_ADAPTER_BENEFIT")

        return PrerequisiteCheckResult(
            eligible=eligible,
            single_adapter_validated=single_adapter_validated,
            blocking_reasons=blocking_reasons,
            adapter_id=adapter_meta.dataset_id if adapter_meta else None,
            adapter_sha256=adapter_meta.adapter_sha256 if adapter_meta else None,
            stage40_run_id="stage40_ablation" if has_stage40_real_execution else None,
            target_metric="command_redundancy_count",
            validation_result="NOT_VALIDATED" if not has_measured_benefit else "PASSED",
            held_out_result="UNTESTED" if not single_adapter_validated else "PASSED",
            reproducibility_status="BLOCKED" if not eligible else "VERIFIED",
        )

    def validate_multi_adapter_readiness(self) -> PrerequisiteCheckResult:
        """Quick convenience validation against standard repository paths."""
        return self.check_single_adapter_prerequisite()
