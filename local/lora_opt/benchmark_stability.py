"""Benchmark Stability and Split Reproducibility Auditor for Stage 37 (Section 6).

Verifies that the frozen benchmark split (v1) remains completely stable:
- Source tasks file and SHA-256 digest
- Split manifest (manifest.json) integrity
- Dev, validation, and held-out file digests and task counts
- Held-out lock (held_out.lock) preservation and cryptographic tamper verification
- Disjointness and zero cross-split leakage
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.splits.held_out_lock import verify_held_out_lock
from benchmark.splits.manifests import load_manifest, verify_manifest_integrity
from local.lora_opt.models import BenchmarkStabilityReport, BenchmarkStabilityStatus


class BenchmarkStabilityAuditor:
    """Audits benchmark split v1 stability and held-out integrity."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.splits_dir = self.repo_root / "benchmark" / "splits" / "v1"

    def audit_benchmark_stability(self) -> BenchmarkStabilityReport:
        """Audits the benchmark splits and held-out lock."""
        diagnostics: list[str] = []

        if not self.splits_dir.exists():
            return BenchmarkStabilityReport(
                source_sha256="",
                manifest_sha256="",
                dev_file_sha256="",
                validation_file_sha256="",
                held_out_file_sha256="",
                held_out_lock_sha256="",
                total_tasks_count=0,
                status=BenchmarkStabilityStatus.BENCHMARK_UNAVAILABLE.value,
                diagnostics=[f"Splits directory not found at {self.splits_dir}"],
            )

        manifest_path = self.splits_dir / "manifest.json"
        if not manifest_path.exists():
            return BenchmarkStabilityReport(
                source_sha256="",
                manifest_sha256="",
                dev_file_sha256="",
                validation_file_sha256="",
                held_out_file_sha256="",
                held_out_lock_sha256="",
                total_tasks_count=0,
                status=BenchmarkStabilityStatus.BENCHMARK_CHANGED.value,
                diagnostics=["manifest.json missing from splits directory."],
            )

        manifest = load_manifest(manifest_path)
        is_man_valid, man_errs = verify_manifest_integrity(manifest_path, self.splits_dir)
        if not is_man_valid:
            diagnostics.extend(man_errs)

        dev_path = self.splits_dir / "dev.jsonl"
        val_path = self.splits_dir / "validation.jsonl"
        held_path = self.splits_dir / "held_out.jsonl"
        lock_path = self.splits_dir / "held_out.lock"

        # Held-out lock verification
        is_lock_valid, lock_err = verify_held_out_lock(
            lock_path=lock_path,
            held_out_file_path=held_path,
            current_manifest_sha256=manifest.manifest_sha256,
        )
        if not is_lock_valid:
            diagnostics.append(lock_err)

        # Compute file digests
        source_hash = manifest.source.source_sha256
        man_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

        dev_hash = hashlib.sha256(dev_path.read_bytes()).hexdigest() if dev_path.exists() else ""
        val_hash = hashlib.sha256(val_path.read_bytes()).hexdigest() if val_path.exists() else ""
        held_hash = hashlib.sha256(held_path.read_bytes()).hexdigest() if held_path.exists() else ""
        lock_hash = hashlib.sha256(lock_path.read_bytes()).hexdigest() if lock_path.exists() else ""

        total_tasks = manifest.source.record_count

        # Check expected task counts (dev=67, val=48, held_out=14 -> 129 total)
        dev_count = manifest.splits["dev"].task_count if "dev" in manifest.splits else 0
        val_count = manifest.splits["validation"].task_count if "validation" in manifest.splits else 0
        held_count = manifest.splits["held_out"].task_count if "held_out" in manifest.splits else 0

        if total_tasks != 129 or dev_count != 67 or val_count != 48 or held_count != 14:
            diagnostics.append(
                f"Task count discrepancy: total={total_tasks} (expected 129), "
                f"dev={dev_count} (67), val={val_count} (48), held_out={held_count} (14)."
            )

        is_stable = len(diagnostics) == 0
        status = (
            BenchmarkStabilityStatus.BENCHMARK_STABLE.value
            if is_stable
            else BenchmarkStabilityStatus.BENCHMARK_CHANGED.value
        )

        return BenchmarkStabilityReport(
            source_sha256=source_hash,
            manifest_sha256=man_hash,
            dev_file_sha256=dev_hash,
            validation_file_sha256=val_hash,
            held_out_file_sha256=held_hash,
            held_out_lock_sha256=lock_hash,
            total_tasks_count=total_tasks,
            status=status,
            diagnostics=diagnostics,
        )


def verify_benchmark_stability(repo_root: Optional[Path | str] = None) -> BenchmarkStabilityReport:
    """Convenience helper auditing benchmark split reproducibility and held-out lock."""
    auditor = BenchmarkStabilityAuditor(repo_root=repo_root)
    return auditor.audit_benchmark_stability()
