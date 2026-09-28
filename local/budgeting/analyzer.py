"""Tool-call budgeting analyzer and report generator (Stage 26).

Analyzes tool invocation events across runs:
- Call count distributions (per tool, per turn, per task)
- Empirical novelty ratio and average information value
- Waste classification (safe redundant, possibly redundant, necessary repeats)
- Observational success associations (strict non-causal labeling)
- Operational tool budget profiles
- Deterministic markdown report generation
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from local.budgeting.models import (
    EvidenceNovelty,
    ToolAssociation,
    ToolBudgetProfile,
    ToolCallCategory,
    ToolCallEvent,
    ToolDistributionMetrics,
    ToolSuccessAssociation,
    WasteClassification,
)


class ToolBudgetAnalyzer:
    """Aggregates tool call events to generate observational budgeting metrics.
    
    Guarantees:
    - Never makes causal claims from observational correlation.
    - Accurately counts distinct vs repeated calls and empirical novelty.
    """

    def __init__(self) -> None:
        self._events: list[ToolCallEvent] = []
        # task_id -> success: bool | None
        self._task_outcomes: dict[str, bool | None] = {}

    def record_event(self, event: ToolCallEvent) -> None:
        """Records a completed tool call execution event."""
        self._events.append(event)

    def record_task_outcome(self, task_id: str, success: bool | None) -> None:
        """Records whether a task run ended in success (resolved) or failure."""
        self._task_outcomes[task_id] = success

    def total_calls(self) -> int:
        """Returns total number of recorded tool call events."""
        return len(self._events)

    def calculate_tool_distributions(self) -> dict[str, ToolDistributionMetrics]:
        """Calculates call count, repeated ratio, and novelty metrics per tool."""
        by_tool: dict[str, list[ToolCallEvent]] = defaultdict(list)
        for ev in self._events:
            by_tool[ev.tool_name].append(ev)

        total_all_calls = max(len(self._events), 1)
        results: dict[str, ToolDistributionMetrics] = {}

        for tool_name, events in sorted(by_tool.items()):
            cat = events[0].category if events else ToolCallCategory.READ_OBSERVATION
            total_c = len(events)
            
            # Count distinct argument signatures
            seen_digests: set[str] = set()
            distinct_c = 0
            repeated_c = 0
            for e in events:
                # Key by (args_digest, repo_state_id)
                d_key = f"{e.normalized_arguments}|{e.repository_state_id}"
                if d_key not in seen_digests:
                    seen_digests.add(d_key)
                    distinct_c += 1
                else:
                    repeated_c += 1

            cache_hits = sum(1 for e in events if e.cache_hit)
            cache_misses = sum(1 for e in events if not e.cache_hit)
            new_ev = sum(1 for e in events if e.information_value.novelty_class == EvidenceNovelty.NEW_EVIDENCE)
            no_new_ev = sum(1 for e in events if e.information_value.novelty_class == EvidenceNovelty.NO_NEW_EVIDENCE)
            safe_red = sum(1 for e in events if e.waste_class == WasteClassification.SAFE_REDUNDANT)
            poss_red = sum(1 for e in events if e.waste_class == WasteClassification.POSSIBLY_REDUNDANT)
            nec_rep = sum(1 for e in events if e.waste_class == WasteClassification.NECESSARY_REPEAT)
            unk_waste = sum(1 for e in events if e.waste_class == WasteClassification.UNKNOWN)

            info_ratios = [e.information_value.novelty_ratio for e in events]
            avg_info = sum(info_ratios) / max(len(info_ratios), 1)

            share_pct = round((total_c / total_all_calls) * 100.0, 2)

            results[tool_name] = ToolDistributionMetrics(
                tool_name=tool_name,
                category=cat,
                total_calls=total_c,
                distinct_calls=distinct_c,
                repeated_calls=repeated_c,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                new_evidence_calls=new_ev,
                no_new_evidence_calls=no_new_ev,
                safe_redundant_calls=safe_red,
                possibly_redundant_calls=poss_red,
                necessary_repeat_calls=nec_rep,
                unknown_waste_calls=unk_waste,
                average_information_ratio=round(avg_info, 3),
                call_share_percent=share_pct,
            )

        return results

    def calculate_success_associations(self) -> dict[str, ToolSuccessAssociation]:
        """Calculates observational tool usage metrics grouped by task resolution outcome.
        
        Strict Non-Causal Policy:
        Results denote association only, never asserting that a tool caused success.
        """
        by_tool: dict[str, list[ToolCallEvent]] = defaultdict(list)
        for ev in self._events:
            by_tool[ev.tool_name].append(ev)

        # Count successful vs unsuccessful tasks
        success_tasks = {t for t, succ in self._task_outcomes.items() if succ is True}
        failed_tasks = {t for t, succ in self._task_outcomes.items() if succ is False}
        total_resolved_tasks = len(success_tasks) + len(failed_tasks)

        associations: dict[str, ToolSuccessAssociation] = {}

        for tool_name, events in sorted(by_tool.items()):
            succ_calls = [e for e in events if e.task_id in success_tasks]
            fail_calls = [e for e in events if e.task_id in failed_tasks]

            new_ev_succ = sum(1 for e in succ_calls if e.information_value.novelty_class == EvidenceNovelty.NEW_EVIDENCE)
            new_ev_fail = sum(1 for e in fail_calls if e.information_value.novelty_class == EvidenceNovelty.NEW_EVIDENCE)

            avg_succ = len(succ_calls) / max(len(success_tasks), 1) if success_tasks else 0.0
            avg_fail = len(fail_calls) / max(len(failed_tasks), 1) if failed_tasks else 0.0

            # Observational association status
            if total_resolved_tasks == 0 or (len(succ_calls) == 0 and len(fail_calls) == 0):
                status = ToolAssociation.INSUFFICIENT_DATA
            elif len(succ_calls) > 0 and len(fail_calls) == 0:
                status = ToolAssociation.ASSOCIATED_WITH_SUCCESS
            elif len(fail_calls) > 0 and len(succ_calls) == 0:
                status = ToolAssociation.ASSOCIATED_WITH_FAILURE
            else:
                status = ToolAssociation.ASSOCIATED_WITH_SUCCESS if avg_succ >= avg_fail else ToolAssociation.ASSOCIATED_WITH_FAILURE

            associations[tool_name] = ToolSuccessAssociation(
                tool_name=tool_name,
                successful_task_calls=len(succ_calls),
                unsuccessful_task_calls=len(fail_calls),
                avg_calls_per_successful_task=round(avg_succ, 2),
                avg_calls_per_unsuccessful_task=round(avg_fail, 2),
                new_evidence_on_success=new_ev_succ,
                new_evidence_on_failure=new_ev_fail,
                calls_before_resolution=len(succ_calls),
                calls_during_recovery=sum(1 for e in events if e.related_failure_class is not None),
                association_status=status,
            )

        return associations

    def generate_tool_budget_profiles(self) -> dict[str, ToolBudgetProfile]:
        """Generates operational budget profiles for all observed tools."""
        dists = self.calculate_tool_distributions()
        profiles: dict[str, ToolBudgetProfile] = {}

        for tool_name, m in dists.items():
            profiles[tool_name] = ToolBudgetProfile(
                tool_name=tool_name,
                category=m.category,
                observed_call_count=m.total_calls,
                cache_hits=m.cache_hits,
                cache_misses=m.cache_misses,
                duplicate_count=m.repeated_calls,
                new_evidence_count=m.new_evidence_calls,
                no_new_evidence_count=m.no_new_evidence_calls,
                average_information_value=m.average_information_ratio,
                soft_limit=None,
                hard_limit=None,
                enforcement_enabled=False,  # Observational only in Stage 26
            )

        return profiles

    def generate_markdown_report(self) -> str:
        """Generates a structured markdown report of tool call distributions and metrics."""
        dists = self.calculate_tool_distributions()
        assocs = self.calculate_success_associations()

        lines: list[str] = [
            "# Stage 26: Tool-Call Budgeting Analysis Report",
            "",
            "## 1. Overview",
            f"- **Total Tool Calls Analyzed:** {self.total_calls()}",
            f"- **Unique Tools Invoked:** {len(dists)}",
            "- **Evaluation Framework:** Observational & Deterministic (Non-Causal)",
            "",
            "## 2. Tool Call Count Distribution",
            "",
            "| Tool Name | Category | Calls | Share % | Distinct | Repeated | Cache Hits | Avg Info Ratio |",
            "|---|---|---|---|---|---|---|---|",
        ]

        for t_name, d in dists.items():
            lines.append(
                f"| `{t_name}` | {d.category.value} | {d.total_calls} | {d.call_share_percent}% | "
                f"{d.distinct_calls} | {d.repeated_calls} | {d.cache_hits} | {d.average_information_ratio} |"
            )

        lines.extend([
            "",
            "## 3. Waste & Redundancy Classification",
            "",
            "| Tool Name | Safe Redundant | Possibly Redundant | Necessary Repeat | Unknown |",
            "|---|---|---|---|---|",
        ])

        for t_name, d in dists.items():
            lines.append(
                f"| `{t_name}` | {d.safe_redundant_calls} | {d.possibly_redundant_calls} | "
                f"{d.necessary_repeat_calls} | {d.unknown_waste_calls} |"
            )

        lines.extend([
            "",
            "## 4. Success Contribution Analysis (Observational)",
            "",
            "> [!NOTE]",
            "> Correlations between tool invocation and task success are strictly observational.",
            "> They do not imply that invoking a tool caused the task to be resolved.",
            "",
            "| Tool Name | Success Calls | Failure Calls | Avg/Success Task | Avg/Failure Task | Association Status |",
            "|---|---|---|---|---|---|",
        ])

        for t_name, a in assocs.items():
            lines.append(
                f"| `{t_name}` | {a.successful_task_calls} | {a.unsuccessful_task_calls} | "
                f"{a.avg_calls_per_successful_task} | {a.avg_calls_per_unsuccessful_task} | "
                f"`{a.association_status.value}` |"
            )

        return "\n".join(lines)
