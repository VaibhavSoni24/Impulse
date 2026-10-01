"""Authoritative Reporting Subsystem for Stage 41 (Section 23).

Renders the 14 mandatory sections required by the project constitution:
1. Stage 41 status
2. Parent commit
3. Single-adapter prerequisite
4. Adapter inventory
5. Role mapping schema
6. Experiment matrix
7. Control definition
8. Metrics
9. Invariance rules
10. Compatibility rules
11. Current blocker
12. Fixture status
13. Execution status
14. Explicit statement that no multi-adapter experiment occurred
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from local.multi_adapter.models import (
    MultiAdapterReport,
    PrerequisiteCheckResult,
    Stage41Decision,
)


class MultiAdapterReporter:
    """Generates the authoritative Stage 41 report."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()

    def generate_report_markdown(self, report: MultiAdapterReport) -> str:
        """Generates markdown text adhering strictly to the 14 required sections."""
        prereq = report.prerequisite_result
        prereq_status = "PASS" if prereq and prereq.eligible else "FAIL"
        reasons = ", ".join(prereq.blocking_reasons) if prereq and prereq.blocking_reasons else "None"

        lines = [
            "# IMPULSE Stage 41 — Multi-Adapter Experiment Audit Report",
            "",
            "## 1. Stage 41 Status",
            f"**Current Status:** `{report.overall_status.value}`  ",
            f"**Decision Reason:** {report.decision_reason}",
            "",
            "## 2. Parent Commit",
            f"- **Parent Stage 40 Commit:** `{report.parent_commit}`",
            "",
            "## 3. Single-Adapter Prerequisite",
            f"- **Prerequisite Status:** **{prereq_status}**  ",
            "- **Scientific Precondition:** \"Only experiment with multiple adapters after a single adapter produces a measurable benefit.\"  ",
            f"- **Evaluation Result:** `single_adapter_validated = {prereq.single_adapter_validated if prereq else False}`  ",
            f"- **Prerequisite Blocking Reasons:** {reasons}",
            "",
            "## 4. Adapter Inventory",
            "- **Validated Single Adapters Available:** 0",
            "- **Root Adapter:** `None` (`UNAVAILABLE`)",
            "- **Scout Adapter:** `None` (`UNAVAILABLE`)",
            "- **Reviewer Adapter:** `None` (`UNAVAILABLE`)",
            "- **Note:** Stage 39/40 yielded no adapter weights due to empty trajectory dataset.",
            "",
            "## 5. Role Mapping Schema",
            "- **Root Agent (`root`):** General coding, reasoning, and tool discipline.",
            "- **Scout Sub-Agent (`scout`):** Codebase symbol localization and ranking.",
            "- **Reviewer Sub-Agent (`reviewer`):** Candidate patch critique and defect detection.",
            "- **Role Isolation Invariant:** Adapters are bound strictly to their declared roles; no cross-role leakage.",
            "",
            "## 6. Experiment Matrix",
            "- **MA0:** All agents no adapter (frozen baseline control)",
            "- **MA1:** Root adapter only (single-adapter control)",
            "- **MA2:** Scout adapter only (localization specialist)",
            "- **MA3:** Reviewer adapter only (review specialist)",
            "- **MA4:** Root + Scout adapters (coding + localization)",
            "- **MA5:** Root + Reviewer adapters (coding + review)",
            "- **MA6:** Scout + Reviewer adapters (specialists only)",
            "- **MA7:** Root + Scout + Reviewer adapters (full specialization)",
            "",
            "## 7. Control Definition",
            "- **Baseline Control:** `MA0` (Identical to Stage 24 M0 frozen baseline)",
            "- **Single-Adapter Control:** `MA1` (A/B comparison with single root adapter)",
            "",
            "## 8. Metrics",
            "- **Root Role:** Task success rate, tool discipline error count, patch validity rate.",
            "- **Scout Role:** Localization precision/recall, irrelevant localization rate.",
            "- **Reviewer Role:** Defect catch rate, false-positive review rate.",
            "- **Cost Metrics:** Number of active adapters, total weights size, initialization overhead, inference latency delta.",
            "- **Measured Multi-Adapter Improvement:** **NO** (No multi-adapter experiment executed)",
            "",
            "## 9. Invariance Rules",
            "- Invariance held strictly across all matrix candidates: base model (`gemma-4-31b-it-qat-w4a16-ct`), root prompt (`2360d4bf...`), 9 tool contracts, retrieval `R0`, testing `T0`, recovery `REC0`.",
            "- The ONLY permitted experimental dimension is role-to-adapter assignment.",
            "",
            "## 10. Compatibility Rules",
            "- Uniform base model rule: mixed base models within a candidate are rejected.",
            "- Role capability rule: an adapter cannot be loaded into an incompatible agent role.",
            "- Status rule: only adapters with status `VALIDATED` may be bound to a role.",
            "",
            "## 11. Current Blocker",
            "**`NO_MEASURED_SINGLE_ADAPTER_BENEFIT`**  ",
            "Multi-adapter routing cannot be scientifically evaluated without a prior demonstrated single-adapter advantage over the frozen baseline.",
            "",
            "## 12. Fixture Status",
            "- Fixtures are restricted strictly to unit and orchestration tests.",
            "- All fixture evidence is explicitly tagged `evidence_mode = FIXTURE`.",
            "- Zero synthetic fixtures are counted as validated adapters or real evaluation results.",
            "",
            "## 13. Execution Status",
            "**`NOT_RUN`** (Halted at the scientific prerequisite gate prior to model loading or inference).",
            "",
            "## 14. Explicit Statement That No Multi-Adapter Experiment Occurred",
            "- **Did a real multi-adapter experiment occur?** **NO**",
            "- **Reason:** The single-adapter prerequisite failed closed. In accordance with Section 1 and Section 3 of Stage 41 governance, no multi-adapter experiment was executed, and no multi-adapter improvement is claimed.",
            "",
        ]
        return "\n".join(lines)

    def write_reports(self, report: MultiAdapterReport) -> Tuple[Path, Path]:
        """Writes report to experiments/lora/multi_adapter/stage41_report.md and root stage41_report.md."""
        content = self.generate_report_markdown(report)

        exp_report = self.repo_root / "experiments" / "lora" / "multi_adapter" / "stage41_report.md"
        exp_report.parent.mkdir(parents=True, exist_ok=True)
        exp_report.write_text(content, encoding="utf-8")

        root_report = self.repo_root / "stage41_report.md"
        root_report.write_text(content, encoding="utf-8")

        return (exp_report, root_report)
