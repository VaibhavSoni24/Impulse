"""Evidence extraction and normalization for Stage 44 candidate evaluation.

Integrates with:
- SQLite evaluation database (`experiments/evaluation.db`)
- Candidate manifests and historical experiment logs
- Split manifests and clean run records
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from local.evaluation.db import DEFAULT_DB_PATH, get_connection
from local.evaluation.queries import list_runs
from local.promotion.models import EvidenceMode


def fetch_candidate_runs(
    candidate_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    split_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves all recorded runs for candidate_id from evaluation.db."""
    target_path = Path(db_path)
    if not target_path.is_file():
        return []

    try:
        conn = get_connection(target_path)
        runs = list_runs(conn, candidate_id=candidate_id, split_name=split_name)
        conn.close()
        return runs
    except Exception:
        return []


def determine_runs_evidence_mode(
    runs: List[Dict[str, Any]],
    fallback_mode: Optional[str] = None,
) -> str:
    """Classifies empirical grounding mode across run records."""
    if not runs:
        if fallback_mode and fallback_mode in {e.value for e in EvidenceMode}:
            return fallback_mode
        return EvidenceMode.UNAVAILABLE.value

    # Check if all runs are infrastructure-unavailable
    infra_only = True
    fixture_only = True
    for r in runs:
        backend = str(r.get("execution_backend") or "")
        f_class = str(r.get("failure_class") or "")
        status = str(r.get("status") or "")
        source_art = str(r.get("source_artifact") or "")

        is_infra = (
            "unavailable" in backend
            or "infrastructure_unavailable" in f_class
            or "execution_unavailable" in status
        )
        if not is_infra:
            infra_only = False

        is_fixture = (
            "fixture" in source_art.lower()
            or r.get("is_fixture") is True
            or "mock" in backend.lower()
        )
        if not is_fixture:
            fixture_only = False

    if infra_only:
        return EvidenceMode.INFRASTRUCTURE_ONLY.value
    if fixture_only:
        return EvidenceMode.FIXTURE.value

    # If any successful or executed run occurred on live system
    return EvidenceMode.LIVE.value
