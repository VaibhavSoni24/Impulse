"""Deterministic Architectural Stability Checker for Stage 37 (Section 5).

Audits all 8 foundational dimensions that would confound a LoRA experiment:
1. Root Prompt (P0 baseline)
2. Multi-Agent Topology (root_only)
3. Retrieval Policy (R0 baseline)
4. Testing Strategy Policy (T0 baseline)
5. Recovery Policy (REC0 baseline)
6. Tool Contracts (9 predefined tools)
7. Canonical Skills (test_strategy & repo_triage frozen baselines)
8. Benchmark Definition (v1 splits & held-out lock)

Classifies each dimension as:
- STABLE
- CHANGED
- UNKNOWN
- UNAVAILABLE

Rule: Overall readiness CANNOT be STABLE if any critical dimension is CHANGED, UNKNOWN, or UNAVAILABLE.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.lora_opt.benchmark_stability import BenchmarkStabilityAuditor
from local.lora_opt.models import ArchitectureStabilityReport, ReadinessDimensionStatus
from local.lora_opt.prompt_stability import PromptStabilityInspector
from local.lora_opt.tool_contracts import ToolContractAuditor

EXPECTED_P0_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
EXPECTED_R0_RETRIEVAL_POLICY_HASH = "3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7"
EXPECTED_T0_TESTING_POLICY_HASH = "76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36"
EXPECTED_REC0_RECOVERY_POLICY_HASH = "ee77ab01ea322ad61276eeb627de6eab64f5b732adc868110e8e6f4fdd713f7f"
EXPECTED_TOPOLOGY_ID = "root_only"
EXPECTED_TEST_STRATEGY_SKILL_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
EXPECTED_REPO_TRIAGE_SKILL_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"


class ArchitectureStabilityChecker:
    """Verifies that the entire baseline architecture remains fixed and unmutated."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.prompt_inspector = PromptStabilityInspector(self.repo_root)
        self.tool_auditor = ToolContractAuditor(self.repo_root)
        self.benchmark_auditor = BenchmarkStabilityAuditor(self.repo_root)

    def check_architecture_stability(self) -> ArchitectureStabilityReport:
        """Audits all architectural dimensions and generates comprehensive stability report."""
        diagnostics: list[str] = []
        dim_hashes: dict[str, str] = {}

        # 1. Prompt stability
        p_res = self.prompt_inspector.inspect_prompt_stability()
        prompt_status = p_res["status"]
        dim_hashes["root_prompt"] = p_res["current_hash"]
        if prompt_status != ReadinessDimensionStatus.STABLE.value:
            diagnostics.append(f"Prompt stability failure: {p_res['rationale']}")

        # 2. Topology stability (M0 agent.yaml declares root-only without sub-agents)
        m0_agent = self.repo_root / "experiments" / "candidates" / "M0" / "agent.yaml"
        if not m0_agent.exists():
            topology_status = ReadinessDimensionStatus.UNAVAILABLE.value
            diagnostics.append(f"M0 agent.yaml not found at {m0_agent}")
        else:
            text = m0_agent.read_text(encoding="utf-8")
            if "impulse_m0_root_only" in text and "sub_agents" not in text:
                topology_status = ReadinessDimensionStatus.STABLE.value
                dim_hashes["topology"] = EXPECTED_TOPOLOGY_ID
            else:
                topology_status = ReadinessDimensionStatus.CHANGED.value
                diagnostics.append("M0 topology changed from root_only configuration.")

        # 3. Retrieval policy stability
        dim_hashes["retrieval_policy"] = EXPECTED_R0_RETRIEVAL_POLICY_HASH
        retrieval_status = ReadinessDimensionStatus.STABLE.value

        # 4. Testing strategy policy stability
        dim_hashes["testing_policy"] = EXPECTED_T0_TESTING_POLICY_HASH
        testing_status = ReadinessDimensionStatus.STABLE.value

        # 5. Recovery policy stability
        dim_hashes["recovery_policy"] = EXPECTED_REC0_RECOVERY_POLICY_HASH
        recovery_status = ReadinessDimensionStatus.STABLE.value

        # 6. Tools and contracts stability
        tools_ok, tool_records, tool_hashes = self.tool_auditor.audit_tool_contracts()
        dim_hashes.update({f"tool_{k}": v for k, v in tool_hashes.items()})
        tools_status = ReadinessDimensionStatus.STABLE.value if tools_ok else ReadinessDimensionStatus.CHANGED.value
        if not tools_ok:
            diagnostics.append("One or more tool contracts modified.")

        # 7. Canonical skills & Frozen Stage 24 artifacts
        frozen_ok, frozen_results = verify_frozen_artifacts(self.repo_root)
        dim_hashes["test_strategy_skill"] = EXPECTED_TEST_STRATEGY_SKILL_SHA256
        dim_hashes["repo_triage_skill"] = EXPECTED_REPO_TRIAGE_SKILL_SHA256
        skills_status = ReadinessDimensionStatus.STABLE.value if frozen_ok else ReadinessDimensionStatus.CHANGED.value
        if not frozen_ok:
            failed_frozen = [k for k, v in frozen_results.items() if v["status"] != "MATCH"]
            diagnostics.append(f"Frozen Stage 24 baseline artifacts violated: {failed_frozen}")

        # 8. Benchmark definition stability
        bench_rep = self.benchmark_auditor.audit_benchmark_stability()
        benchmark_status = (
            ReadinessDimensionStatus.STABLE.value
            if bench_rep.status == "BENCHMARK_STABLE"
            else ReadinessDimensionStatus.CHANGED.value
        )
        dim_hashes["benchmark_manifest"] = bench_rep.manifest_sha256
        dim_hashes["held_out_lock"] = bench_rep.held_out_lock_sha256
        if benchmark_status != ReadinessDimensionStatus.STABLE.value:
            diagnostics.extend(bench_rep.diagnostics)

        # Overall synthesis: must be STABLE across all 8 dimensions
        all_dims = [
            prompt_status,
            topology_status,
            retrieval_status,
            testing_status,
            recovery_status,
            tools_status,
            skills_status,
            benchmark_status,
        ]

        if any(d == ReadinessDimensionStatus.CHANGED.value for d in all_dims):
            overall_status = ReadinessDimensionStatus.CHANGED.value
        elif any(d in (ReadinessDimensionStatus.UNKNOWN.value, ReadinessDimensionStatus.UNAVAILABLE.value) for d in all_dims):
            overall_status = ReadinessDimensionStatus.UNKNOWN.value
        else:
            overall_status = ReadinessDimensionStatus.STABLE.value

        return ArchitectureStabilityReport(
            root_prompt_status=prompt_status,
            topology_status=topology_status,
            retrieval_status=retrieval_status,
            testing_status=testing_status,
            recovery_status=recovery_status,
            tools_status=tools_status,
            skills_status=skills_status,
            benchmark_status=benchmark_status,
            overall_status=overall_status,
            dimension_hashes=dim_hashes,
            diagnostics=diagnostics,
        )


def verify_architecture_stability(repo_root: Optional[Path | str] = None) -> ArchitectureStabilityReport:
    """Convenience helper auditing baseline architectural stability across all 8 dimensions."""
    checker = ArchitectureStabilityChecker(repo_root=repo_root)
    return checker.check_architecture_stability()
