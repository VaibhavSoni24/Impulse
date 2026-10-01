"""Quality Evaluation and Filtering Engine (Stage 38 Section 3, 10, 18, 19).

Enforces strict quality dimensions for OBJ-TOOL-DISCIPLINE:
- Evidence completeness
- Objective alignment (strictly OBJ-TOOL-DISCIPLINE)
- Trajectory completeness
- Tool specificity
- Outcome verifiability
- Provenance completeness
- Safety status (Zero Unsafe Execution Patterns)

Filters and assigns explicit rejection codes:
- REJECT_NO_DECISION_SIGNAL
- REJECT_NO_PROVENANCE
- REJECT_LEAKAGE
- REJECT_SECRET
- REJECT_INFRASTRUCTURE_ONLY
- REJECT_AMBIGUOUS
- REJECT_DUPLICATE
- REJECT_UNSAFE
- REJECT_NOT_PERMITTED
- REJECT_FIXTURE_ISOLATION
- REJECT_OBJECTIVE_MISMATCH
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from local.lora_data.models import (
    EvidenceMode,
    LicenseStatus,
    QualityStatus,
    QualityVector,
    RejectionReason,
)

# Unsafe shell commands that must never be recommended or trained
UNSAFE_COMMAND_PATTERNS = [
    re.compile(r"\brm\s+-(?:r|f|rf|fr)\s+(?:/|\*|~|/\*|/tmp/.*)\b", re.IGNORECASE),
    re.compile(r"\brm\s+-(?:r|f|rf|fr)\b", re.IGNORECASE),
    re.compile(r"\bchmod\s+(?:-R\s+)?777\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=/dev/(?:zero|urandom)\s+of=/dev/", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", re.IGNORECASE),  # fork bomb
    re.compile(r"\bcurl\s+[^|]+\|\s*(?:ba)?sh\b", re.IGNORECASE),
    re.compile(r"\bwget\s+[^|]+\|\s*(?:ba)?sh\b", re.IGNORECASE),
]


class QualityFilter:
    """Evaluates quality vectors and applies authoritative inclusion/rejection gates."""

    def __init__(self) -> None:
        pass

    def check_safety(self, text: str) -> bool:
        """Returns True if text is SAFE, False if it contains dangerous shell patterns."""
        if not text:
            return True
        for pattern in UNSAFE_COMMAND_PATTERNS:
            if pattern.search(text):
                return False
        return True

    def evaluate_example(
        self, example: dict[str, Any], is_fixture_allowed: bool = False
    ) -> tuple[bool, QualityVector, list[str]]:
        """Evaluates an example against all quality and safety criteria.

        Returns:
            (is_accepted, quality_vector, rejection_reasons)
        """
        rejection_reasons: list[str] = []

        # 1. Evidence mode & Fixture isolation check
        ev_mode = example.get("evidence_mode", EvidenceMode.LIVE.value)
        if ev_mode == EvidenceMode.FIXTURE.value and not is_fixture_allowed:
            rejection_reasons.append(RejectionReason.REJECT_FIXTURE_ISOLATION.value)
        elif ev_mode == EvidenceMode.INFRASTRUCTURE_ONLY.value:
            rejection_reasons.append(RejectionReason.REJECT_INFRASTRUCTURE_ONLY.value)

        # 2. Objective alignment check
        obj_id = example.get("objective_id", "")
        if obj_id != "OBJ-TOOL-DISCIPLINE":
            rejection_reasons.append(RejectionReason.REJECT_OBJECTIVE_MISMATCH.value)

        # 3. Provenance and Licensing check
        prov = example.get("provenance", {})
        if not prov or not isinstance(prov, dict):
            rejection_reasons.append(RejectionReason.REJECT_NO_PROVENANCE.value)
        else:
            allowed = prov.get("allowed_for_training", False)
            lic_status = prov.get("license_status", LicenseStatus.UNKNOWN.value)
            if not allowed or lic_status not in (
                LicenseStatus.PERMITTED.value,
                LicenseStatus.PERMITTED_WITH_ATTRIBUTION.value,
            ):
                rejection_reasons.append(RejectionReason.REJECT_NOT_PERMITTED.value)

        # 4. Decision signal check
        pref = example.get("preferred_behavior", {})
        neg = example.get("negative_behavior", {})
        if not pref and not neg:
            rejection_reasons.append(RejectionReason.REJECT_NO_DECISION_SIGNAL.value)
        elif pref and not pref.get("action"):
            rejection_reasons.append(RejectionReason.REJECT_AMBIGUOUS.value)

        # 5. Safety check
        all_texts: list[str] = [
            str(example.get("situation", "")),
            str(example.get("validation_signal", "")),
        ]
        for step in example.get("tool_sequence", []):
            all_texts.append(str(step.get("arguments", "")))
        if pref:
            all_texts.append(str(pref.get("action", "")))
            all_texts.append(str(pref.get("arguments", "")))
        if neg:
            all_texts.append(str(neg.get("action", "")))
            all_texts.append(str(neg.get("arguments", "")))

        combined = " \n ".join(all_texts)
        if not self.check_safety(combined):
            rejection_reasons.append(RejectionReason.REJECT_UNSAFE.value)

        # Compute QualityVector scores
        evidence_completeness = 1.0 if len(example.get("evidence", [])) >= 1 else 0.5
        objective_alignment = 1.0 if obj_id == "OBJ-TOOL-DISCIPLINE" else 0.0
        trajectory_completeness = 1.0 if len(example.get("tool_sequence", [])) >= 1 else 0.7
        tool_specificity = 1.0 if any(s.get("tool_name") for s in example.get("tool_sequence", [])) else 0.6
        outcome_verifiability = 1.0 if example.get("validation_signal") else 0.6
        prov_completeness = 1.0 if (prov and prov.get("license") and prov.get("source_name")) else 0.0
        safety_status = "UNSAFE" if (RejectionReason.REJECT_UNSAFE.value in rejection_reasons) else "SAFE"

        qvec = QualityVector(
            evidence_completeness=evidence_completeness,
            objective_alignment=objective_alignment,
            trajectory_completeness=trajectory_completeness,
            tool_specificity=tool_specificity,
            outcome_verifiability=outcome_verifiability,
            provenance_completeness=prov_completeness,
            safety_status=safety_status,
        )

        if not qvec.is_eligible() and not rejection_reasons:
            rejection_reasons.append(RejectionReason.REJECT_AMBIGUOUS.value)

        is_accepted = len(rejection_reasons) == 0
        return is_accepted, qvec, rejection_reasons
