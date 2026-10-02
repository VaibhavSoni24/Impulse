"""Configuration validity and multi-dimension confounding audit for Stage 44.

Enforces:
- Model permission constraints (single approved base model)
- Secret scanning across full candidate configuration
- Confounding multi-dimension changes (Section 14 & 15)
- Submission package validity and structural integrity
- Adapter and Release-Candidate artifact verification
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from local.promotion.models import (
    ConfigurationEvaluationResult,
    GateDimensionStatus,
)
from local.versioning.comparison import CandidateComparator
from local.versioning.hashing import scan_for_secrets
from local.versioning.models import CandidateManifest
from local.versioning.validation import CandidateValidator
from scripts.validate_submission import SubmissionValidator

PERMITTED_BASE_MODELS = {"gemma-4-31b-it-qat-w4a16-ct"}

ALLOWED_MULTI_DIM_TYPES = {
    "combined_ablation",
    "competition_candidate",
    "specialist_topology",
    "recovery_optimization",
    "packaging",
}


def evaluate_configuration(
    candidate_manifest: CandidateManifest,
    baseline_manifest: Optional[CandidateManifest] = None,
    repo_root: Optional[Path] = None,
) -> ConfigurationEvaluationResult:
    """Evaluates whether candidate configuration conforms to architectural and experimental rules."""
    root = repo_root or Path(__file__).resolve().parent.parent.parent
    notes_list: List[str] = []
    missing_files: List[str] = []

    # 1. Base model validation
    if candidate_manifest.base_model not in PERMITTED_BASE_MODELS:
        return ConfigurationEvaluationResult(
            dimension_status=GateDimensionStatus.FAIL.value,
            submission_valid=False,
            manifest_valid=False,
            model_permitted=False,
            is_multi_dimension=False,
            multi_dimension_allowed=False,
            secrets_found=False,
            missing_files=[],
            notes=f"Disallowed base model: '{candidate_manifest.base_model}'. Permitted: {sorted(PERMITTED_BASE_MODELS)}.",
        )

    # 2. Secret scanning
    secrets_found = False
    try:
        scan_for_secrets(candidate_manifest.to_dict())
    except Exception as exc:
        secrets_found = True
        return ConfigurationEvaluationResult(
            dimension_status=GateDimensionStatus.FAIL.value,
            submission_valid=False,
            manifest_valid=False,
            model_permitted=True,
            is_multi_dimension=False,
            multi_dimension_allowed=False,
            secrets_found=True,
            missing_files=[],
            notes=f"Credential or secret pattern detected in candidate manifest: {exc}",
        )

    # 3. Schema and invariant validation
    manifest_valid = True
    try:
        CandidateValidator.validate_manifest(candidate_manifest)
    except Exception as exc:
        manifest_valid = False
        return ConfigurationEvaluationResult(
            dimension_status=GateDimensionStatus.FAIL.value,
            submission_valid=False,
            manifest_valid=False,
            model_permitted=True,
            is_multi_dimension=False,
            multi_dimension_allowed=False,
            secrets_found=False,
            missing_files=[],
            notes=f"Candidate manifest validation failed: {exc}",
        )

    # 4. Multi-dimension confounding check
    is_multi_dim = False
    multi_dim_allowed = False
    if baseline_manifest is not None:
        diff = CandidateComparator.compare(baseline_manifest, candidate_manifest)
        is_multi_dim = diff.is_multi_dimension
        exp_type_lower = str(candidate_manifest.experiment_type or "").lower()
        multi_dim_allowed = exp_type_lower in ALLOWED_MULTI_DIM_TYPES

        if is_multi_dim and not multi_dim_allowed:
            return ConfigurationEvaluationResult(
                dimension_status=GateDimensionStatus.FAIL.value,
                submission_valid=False,
                manifest_valid=True,
                model_permitted=True,
                is_multi_dimension=True,
                multi_dimension_allowed=False,
                secrets_found=False,
                missing_files=[],
                notes=(
                    f"Confounding multi-dimension experiment rejected: altered dimensions {diff.changed_dimensions} "
                    f"without declaring experiment_type='combined_ablation'."
                ),
            )

    # 5. Adapter artifact check
    if candidate_manifest.primary_dimension == "adapter" or candidate_manifest.adapter_id:
        adapter_path_str = candidate_manifest.adapter_id
        if not adapter_path_str or adapter_path_str in ("UNKNOWN", "UNAVAILABLE", "NONE"):
            missing_files.append("adapter_weights")
            return ConfigurationEvaluationResult(
                dimension_status=GateDimensionStatus.FAIL.value,
                submission_valid=False,
                manifest_valid=True,
                model_permitted=True,
                is_multi_dimension=is_multi_dim,
                multi_dimension_allowed=multi_dim_allowed,
                secrets_found=False,
                missing_files=["adapter_weights"],
                notes=f"Adapter candidate '{candidate_manifest.candidate_id}' references no valid adapter artifact.",
            )
        # Check adapter file existence on disk
        adapter_file = root / adapter_path_str if not Path(adapter_path_str).is_absolute() else Path(adapter_path_str)
        if not adapter_file.is_file():
            missing_files.append(str(adapter_file))
            return ConfigurationEvaluationResult(
                dimension_status=GateDimensionStatus.FAIL.value,
                submission_valid=False,
                manifest_valid=True,
                model_permitted=True,
                is_multi_dimension=is_multi_dim,
                multi_dimension_allowed=multi_dim_allowed,
                secrets_found=False,
                missing_files=missing_files,
                notes=f"Referenced adapter weights file not found: {adapter_file}.",
            )

    # 6. Release candidate configuration check
    if candidate_manifest.candidate_id == "RC1":
        if candidate_manifest.status == "RESERVED" or candidate_manifest.result_status == "RESERVED_IDENTITY":
            return ConfigurationEvaluationResult(
                dimension_status=GateDimensionStatus.UNKNOWN.value,
                submission_valid=False,
                manifest_valid=True,
                model_permitted=True,
                is_multi_dimension=is_multi_dim,
                multi_dimension_allowed=multi_dim_allowed,
                secrets_found=False,
                missing_files=[],
                notes="NO_RELEASE_CANDIDATE_CONFIGURATION: RC1 is a reserved release-candidate identity.",
            )

    # 7. Submission package structural validator (for submission candidates M0-M5 or candidates with agent.yaml)
    cand_dir = root / "experiments" / "candidates" / candidate_manifest.candidate_id
    submission_valid = True
    if (cand_dir / "agent.yaml").is_file() or (cand_dir / "agent.yml").is_file():
        sub_val = SubmissionValidator(cand_dir)
        submission_valid = sub_val.validate()
        if not submission_valid:
            return ConfigurationEvaluationResult(
                dimension_status=GateDimensionStatus.FAIL.value,
                submission_valid=False,
                manifest_valid=True,
                model_permitted=True,
                is_multi_dimension=is_multi_dim,
                multi_dimension_allowed=multi_dim_allowed,
                secrets_found=False,
                missing_files=[],
                notes=f"Submission packaging validator failed: {sub_val.errors[:3]}.",
            )

    return ConfigurationEvaluationResult(
        dimension_status=GateDimensionStatus.PASS.value,
        submission_valid=submission_valid,
        manifest_valid=True,
        model_permitted=True,
        is_multi_dimension=is_multi_dim,
        multi_dimension_allowed=multi_dim_allowed,
        secrets_found=False,
        missing_files=[],
        notes="Configuration valid: schema verified, permitted base model, clean diff, zero secrets.",
    )
