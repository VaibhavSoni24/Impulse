"""No-Progress Detection module (Stage 19 / Candidate E10).

Exports progress statuses, reasons, cycle snapshot models, and deterministic detector.
"""

from local.progress.detector import NoProgressDetectorV1
from local.progress.models import (
    CycleSnapshot,
    NoProgressReason,
    ProgressAssessment,
    ProgressStatus,
    normalize_code_edit,
    normalize_text,
)

__all__ = [
    "CycleSnapshot",
    "NoProgressDetectorV1",
    "NoProgressReason",
    "ProgressAssessment",
    "ProgressStatus",
    "normalize_code_edit",
    "normalize_text",
]
