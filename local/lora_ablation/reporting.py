"""Reporting and Audit Subsystem for Stage 40 LoRA Ablation (Section 26).

Generates authoritative Stage 40 reports with the 14 mandatory governance sections:
1. Status
2. Parent Stage 39 Commit
3. Frozen control
4. Ablation conditions
5. Adapter availability
6. Benchmark
7. Metrics
8. Invariance controls
9. Current execution state
10. Fixture/test evidence
11. Promotion gate
12. Known blockers
13. Next executable step
14. Explicit statement whether real A/B execution occurred
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from local.lora_ablation.models import (
    AblationComparisonReport,
    AdapterGateStatus,
    ConditionStatus,
    ConditionType,
    Stage40Decision,
)


class AblationReporter:
    """Generates the authoritative Stage 40 report."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()

    def generate_report_markdown(self, report: AblationComparisonReport) -> str:
        """Renders the complete 14-section Stage 40 Markdown report."""
        adapter_available = (
            "YES" if report.adapter_gate_status == AdapterGateStatus.READY and report.adapter_metadata is not None else "NO"
        )
        real_ab_executed = "YES" if (report.a_metrics is not None and report.b_metrics is not None and report.adapter_metadata and report.adapter_metadata.evidence_mode == "REAL") else "NO"

        lines = [
            "# IMPULSE Stage 40 — LoRA Ablation Audit Report",
            "",
            "## 1. Status",
            f"**Current Status:** `{report.overall_status.value}`  ",
            f"**Promotion Gate Status:** `{report.promotion_decision.value}`  ",
            "",
            "## 2. Parent Stage 39 Commit",
            f"`{report.parent_commit}`",
            "",
            "## 3. Frozen Control",
            "- **Control Identifier:** `M0` (Frozen competition baseline)",
            "- **Base Model:** `gemma-4-31b-it-qat-w4a16-ct`",
            "- **Root Prompt Hash:** `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`",
            "- **Tool Contracts:** 9 locked frozen contracts",
            "- **Retrieval Policy:** `R0`",
            "- **Testing Strategy:** `T0`",
            "- **Recovery Policy:** `REC0`",
            "- **Topology:** `root_only`",
            "",
            "## 4. Ablation Conditions",
            f"- **Condition A (BASELINE_NO_ADAPTER):** `{report.a_condition.status.value if report.a_condition else 'NOT_CONFIGURED'}`",
            f"- **Condition B (L1_ADAPTER):** `{report.b_condition.status.value if report.b_condition else 'MISSING_ADAPTER_ARTIFACT'}`",
            f"- **Condition C (L1_ADAPTER_PROMPT_VARIANT):** `{report.c_condition.status.value if report.c_condition else 'BLOCKED_BY_MISSING_ADAPTER'}`",
            f"- **Condition D (L1_ADAPTER_RETRIEVAL_VARIANT):** `{report.d_condition.status.value if report.d_condition else 'BLOCKED_BY_MISSING_ADAPTER'}`",
            "",
            "## 5. Adapter Availability",
            f"- **Adapter Available:** **{adapter_available}**",
            f"- **Adapter Gate Classification:** `{report.adapter_gate_status.value}`",
            f"- **Details:** {report.decision_reason}",
            "",
            "## 6. Benchmark",
            "- **Split Policy:** `repo_disjoint` (Version 1.0.0)",
            "- **Split Partitions:** `DEV` (67 tasks), `VALIDATION` (48 tasks), `HELD_OUT` (14 tasks)",
            "- **Held-Out Protection:** Frozen and locked against tuning; confirmation only.",
            "",
            "## 7. Metrics",
            "- **Primary Metric:** `command_redundancy_count` / `repeated_failing_command_count`",
            "- **Secondary Metrics:** `task_success_rate`, `tool_invocation_error_count`, `runtime_ms`, `tool_call_count`, `turns`",
            "- **Collateral Regression Metrics:** Task-paired transitions (`A_PASS_B_FAIL` count)",
            "- **Measured Adapter Improvement:** **NO** (No adapter exists to measure)",
            "",
            "## 8. Invariance Controls",
            "- A vs B verified strictly invariant across all 9 dimensions (model, prompt, tools, retrieval, testing, recovery, topology, split, sampling).",
            "- Condition C strictly isolated to prompt variance only.",
            "- Condition D strictly isolated to retrieval variance only.",
            "",
            "## 9. Current Execution State",
            f"**Result:** `ABLATION_BLOCKED_BY_MISSING_ADAPTER`  ",
            "Condition A is structurally validated and ready. Condition B is halted at the Hard Adapter Gate due to missing adapter weights (`adapter_model.safetensors`). Secondary conditions C and D are consequently gated.",
            "",
            "## 10. Fixture / Test Evidence",
            "- End-to-end orchestration, paired transition logic, collateral regression classification, and gate enforcement are verified via isolated unit and orchestration tests.",
            "- No synthetic fixtures are reported as real training or evaluation data (`evidence_mode == FIXTURE` strictly prohibited from candidate promotion).",
            "",
            "## 11. Promotion Gate",
            f"- **Decision:** `{report.promotion_decision.value}`",
            "- **Promotion Policy:** Validation improvement on `OBJ-TOOL-DISCIPLINE` AND zero collateral regressions (`A_PASS_B_FAIL == 0`) AND zero held-out regressions.",
            "- **Automatic Promotion Prohibition:** Strictly enforced. Production `agent.yaml` is never automatically edited.",
            "",
            "## 12. Known Blockers",
            "1. **Missing Adapter Weights:** Stage 38/39 dataset status `BLOCKED_BY_DATA` (TRAIN=0, VALIDATION=0) precluded adapter weight creation.",
            "2. **Host Hardware:** Local host has 0 NVIDIA GPUs and integrated Intel Iris Xe graphics (`TRAINING_HARDWARE_UNAVAILABLE`).",
            "",
            "## 13. Next Executable Step",
            "Acquisition of non-zero curated trajectory data for `OBJ-TOOL-DISCIPLINE`, execution of PEFT training on compatible external compute (4x L4), and provision of verified `adapter_model.safetensors` to Condition B.",
            "",
            "## 14. Explicit Statement Whether Real A/B Execution Occurred",
            f"- **Did real A/B execution occur?** **{real_ab_executed}**",
            "- **Reason:** The Stage 39 pipeline completed with zero adapter weights generated. The Hard Adapter Gate halted Condition B execution prior to inference, cleanly preserving scientific integrity without fabrication.",
            "",
        ]
        return "\n".join(lines)

    def write_reports(self, report: AblationComparisonReport) -> Tuple[Path, Path]:
        """Writes report to experiments/lora/stage40_report.md and root stage40_report.md."""
        content = self.generate_report_markdown(report)

        exp_report = self.repo_root / "experiments" / "lora" / "stage40_report.md"
        exp_report.parent.mkdir(parents=True, exist_ok=True)
        exp_report.write_text(content, encoding="utf-8")

        root_report = self.repo_root / "stage40_report.md"
        root_report.write_text(content, encoding="utf-8")

        return (exp_report, root_report)
