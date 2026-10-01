"""Artifact Management and Manifest Persistence for Stage 40 (Section 15, 16).

Handles safe serialization of ablation run manifests, paired comparison records,
and evaluation reports under experiments/lora/ablation/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from local.lora_ablation.models import (
    AblationComparisonReport,
    AblationConditionConfig,
    AblationRunManifest,
)


class AblationArtifactManager:
    """Manages filesystem artifacts and manifests for ablation experiments."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.ablation_dir = self.repo_root / "experiments" / "lora" / "ablation"
        self.runs_dir = self.ablation_dir / "runs"

    def ensure_directories(self) -> None:
        """Creates necessary artifact directories if they do not exist."""
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def write_run_manifest(self, manifest: AblationRunManifest) -> Path:
        """Writes an immutable run manifest to experiments/lora/ablation/runs/<run_id>/manifest.json."""
        self.ensure_directories()
        run_folder = self.runs_dir / manifest.run_id
        run_folder.mkdir(parents=True, exist_ok=True)

        manifest_path = run_folder / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)

        return manifest_path

    def write_comparison_report(self, report: AblationComparisonReport, filename: str = "comparison_report.json") -> Path:
        """Writes structured comparison report JSON."""
        self.ensure_directories()
        out_path = self.ablation_dir / filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, sort_keys=True)
        return out_path

    def write_blocked_record(self, record_data: Dict[str, Any]) -> Path:
        """Writes blocked state record to experiments/lora/ablation_blocked_record.json."""
        out_path = self.repo_root / "experiments" / "lora" / "ablation_blocked_record.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record_data, f, indent=2, sort_keys=True)
        return out_path
