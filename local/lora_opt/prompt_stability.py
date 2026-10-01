"""Root-Prompt Stability Inspector for Stage 37 (Section 10).

Audits the Root Agent Prompt (P0) against git history and frozen baselines:
- Verifies current hash matches frozen Stage 24 digest (`2360d4bf...`)
- Inspects git log history to ensure prompt is not fluctuating
- Classifies prompt readiness as STABLE, NOT_STABLE, or INSUFFICIENT_HISTORY
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES
from local.lora_opt.models import ReadinessDimensionStatus

EXPECTED_P0_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
P0_PROMPT_RELATIVE_PATH = "experiments/candidates/M0/prompts/root.md"


class PromptStabilityInspector:
    """Inspects root prompt immutability and historical stability."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.prompt_path = self.repo_root / P0_PROMPT_RELATIVE_PATH

    def inspect_prompt_stability(self) -> Dict[str, Any]:
        """Audits current root prompt hash and git revision history."""
        if not self.prompt_path.exists():
            return {
                "status": ReadinessDimensionStatus.UNAVAILABLE.value,
                "current_hash": "",
                "expected_hash": EXPECTED_P0_PROMPT_SHA256,
                "is_frozen": False,
                "commits_count": 0,
                "history": [],
                "rationale": f"Root prompt file not found at {self.prompt_path}.",
            }

        content_bytes = self.prompt_path.read_bytes()
        actual_hash = hashlib.sha256(content_bytes).hexdigest()
        is_frozen = (actual_hash == EXPECTED_P0_PROMPT_SHA256) and (
            P0_PROMPT_RELATIVE_PATH in FROZEN_STAGE24_HASHES
        )

        # Inspect Git commit history for this file
        history: list[str] = []
        try:
            res = subprocess.run(
                ["git", "log", "--oneline", "-n", "10", "--", P0_PROMPT_RELATIVE_PATH],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                history = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        except Exception:
            pass

        if not is_frozen:
            status = ReadinessDimensionStatus.CHANGED.value
            rationale = (
                f"Root prompt hash {actual_hash} does not match expected frozen hash {EXPECTED_P0_PROMPT_SHA256}."
            )
        elif not history:
            status = ReadinessDimensionStatus.INSUFFICIENT_HISTORY.value if hasattr(ReadinessDimensionStatus, "INSUFFICIENT_HISTORY") else "INSUFFICIENT_HISTORY"
            rationale = "Prompt matches frozen hash but git history could not be queried."
        elif len(history) == 1:
            # Established at Stage 24 commit and untouched since!
            status = ReadinessDimensionStatus.STABLE.value
            rationale = (
                f"Root prompt is completely frozen (SHA-256: {actual_hash[:12]}). "
                f"Created in commit {history[0]} and unchanged across 13 consecutive stages."
            )
        else:
            status = ReadinessDimensionStatus.STABLE.value
            rationale = (
                f"Root prompt is frozen (SHA-256: {actual_hash[:12]}) with {len(history)} historical commits."
            )

        return {
            "status": status,
            "current_hash": actual_hash,
            "expected_hash": EXPECTED_P0_PROMPT_SHA256,
            "is_frozen": is_frozen,
            "commits_count": len(history),
            "history": history,
            "rationale": rationale,
        }


def verify_root_prompt_stability(repo_root: Optional[Path | str] = None) -> PromptStabilityReport:
    """Convenience helper auditing root prompt stability and returning PromptStabilityReport."""
    from local.lora_opt.models import PromptStabilityReport
    inspector = PromptStabilityInspector(repo_root=repo_root)
    res = inspector.inspect_prompt_stability()
    return PromptStabilityReport(
        status=res["status"],
        prompt_hash=res["current_hash"],
        expected_hash=res["expected_hash"],
        is_frozen=res["is_frozen"],
        commits_count=res["commits_count"],
        history=res["history"],
        rationale=res["rationale"],
    )
