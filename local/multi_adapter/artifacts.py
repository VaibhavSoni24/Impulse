"""Artifact and Configuration Persistence for Stage 41 (Section 7, 23).

Manages experiments/lora/multi_adapter/ directory and machine-readable config.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from local.multi_adapter.models import (
    BASE_MODEL_IDENTIFIER,
    MultiAdapterCandidateConfig,
    MultiAdapterReport,
    MultiAdapterRunManifest,
)


class MultiAdapterArtifactManager:
    """Handles serialization of multi-adapter configurations and manifests."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.multi_dir = self.repo_root / "experiments" / "lora" / "multi_adapter"
        self.runs_dir = self.multi_dir / "runs"

    def ensure_directories(self) -> None:
        """Creates necessary multi-adapter directories."""
        self.multi_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def write_active_config(self, candidate_id: str = "MA1") -> Path:
        """Writes baseline multi-adapter configuration to experiments/lora/multi_adapter/config.json."""
        self.ensure_directories()
        config_path = self.multi_dir / "config.json"
        config_data = {
            "candidate_id": candidate_id,
            "base_model": BASE_MODEL_IDENTIFIER,
            "roles": {
                "root": None,
                "scout": None,
                "reviewer": None,
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, sort_keys=True)
        return config_path

    def write_run_manifest(self, manifest: MultiAdapterRunManifest) -> Path:
        """Writes an immutable run manifest."""
        self.ensure_directories()
        run_folder = self.runs_dir / manifest.run_id
        run_folder.mkdir(parents=True, exist_ok=True)

        manifest_path = run_folder / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
        return manifest_path
