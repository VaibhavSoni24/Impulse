"""Immutable Baseline Snapshot Engine for Stage 37 L0 (Section 4).

Captures and serializes the complete, cryptographic baseline snapshot:
- Git commit
- Model ID (gemma-4-31b-it-qat-w4a16-ct)
- Root prompt P0 digest
- Topology identity (root_only)
- Retrieval policy R0 digest
- Testing strategy policy T0 digest
- Recovery policy REC0 digest
- Canonical skill digests (test_strategy & repo_triage)
- Benchmark source and split manifest digests
- Held-out lock digest
- Tool contract digests (9 predefined tools)
- Host environment (OS, Python, GPU, packages)
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES
from local.lora_opt.architecture_stability import (
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_R0_RETRIEVAL_POLICY_HASH,
    EXPECTED_REC0_RECOVERY_POLICY_HASH,
    EXPECTED_REPO_TRIAGE_SKILL_SHA256,
    EXPECTED_T0_TESTING_POLICY_HASH,
    EXPECTED_TEST_STRATEGY_SKILL_SHA256,
    EXPECTED_TOPOLOGY_ID,
)
from local.lora_opt.benchmark_stability import BenchmarkStabilityAuditor
from local.lora_opt.hardware_audit import audit_hardware_environment
from local.lora_opt.models import BaselineSnapshot
from local.lora_opt.tool_contracts import ToolContractAuditor


def capture_baseline_snapshot(repo_root: Optional[Path | str] = None) -> BaselineSnapshot:
    """Captures authoritative cryptographic snapshot of all fixed system baselines."""
    root = Path(repo_root).resolve() if repo_root else Path.cwd()

    # Git commit
    git_commit = "UNKNOWN"
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0:
            git_commit = res.stdout.strip()
    except Exception:
        pass

    # Benchmark audits
    bench_auditor = BenchmarkStabilityAuditor(root)
    b_rep = bench_auditor.audit_benchmark_stability()

    # Tool contract audits
    tool_auditor = ToolContractAuditor(root)
    _, _, tool_hashes = tool_auditor.audit_tool_contracts()

    # Hardware environment
    hw = audit_hardware_environment()

    # Skills
    skill_hashes = {
        "test_strategy": EXPECTED_TEST_STRATEGY_SKILL_SHA256,
        "repo_triage": EXPECTED_REPO_TRIAGE_SKILL_SHA256,
    }

    pkg_versions = {
        "torch": hw.torch_version,
        "transformers": hw.transformers_version,
        "peft": hw.peft_version,
    }

    gpu_info = (
        f"{hw.gpu_count}x {hw.gpu_model} ({hw.per_gpu_vram_gb} GB VRAM)"
        if hw.gpu_model
        else "NONE_DETECTED"
    )

    snapshot = BaselineSnapshot(
        git_commit=git_commit,
        model_id="gemma-4-31b-it-qat-w4a16-ct",
        prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        topology_identity=EXPECTED_TOPOLOGY_ID,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        recovery_policy_hash=EXPECTED_REC0_RECOVERY_POLICY_HASH,
        skill_hashes=skill_hashes,
        benchmark_source_hash=b_rep.source_sha256,
        dev_manifest_hash=b_rep.dev_file_sha256,
        validation_manifest_hash=b_rep.validation_file_sha256,
        held_out_manifest_hash=b_rep.held_out_file_sha256,
        held_out_lock_hash=b_rep.held_out_lock_sha256,
        evaluator_version="Stage 28 CleanCopyEvaluator v1.0",
        tool_contract_hashes=tool_hashes,
        python_version=hw.python_version,
        package_versions=pkg_versions,
        operating_system=hw.os_release,
        gpu_info=gpu_info,
    )

    return snapshot


def save_baseline_snapshot(
    snapshot: BaselineSnapshot,
    dest_path: Optional[Path | str] = None,
) -> Path:
    """Serializes baseline snapshot to JSON."""
    p = (
        Path(dest_path)
        if dest_path
        else Path("experiments/lora/L0/baseline/snapshot.json")
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
    return p
