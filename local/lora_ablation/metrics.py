"""Objective-Specific Metrics Calculator for Stage 40 LoRA Ablation (Section 10, 13).

Calculates authoritative metrics for OBJ-TOOL-DISCIPLINE:
- repeated_failing_command_count: invocations repeating a command/signature after an
  equivalent failure without intervening file edits or state changes.
- repeated_command_rate: repeated commands / total tool calls
- tool_invocation_error_count: tool invocations with nonzero exit codes or syntax errors
- tool_invocation_error_rate: tool errors / total tool calls
- task_success_rate: tasks solved / total tasks
- failure_class_distribution: breakdown by failure category
- cost metrics: runtime, turns, tool calls, adapter size
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.lora_ablation.models import (
    AblationAggregateMetrics,
    ConditionType,
    TaskEvaluationRecord,
)


class ToolDisciplineMetricsCalculator:
    """Calculates objective-aligned metrics from tool execution traces."""

    @staticmethod
    def calculate_repeated_failing_commands(tool_trace: List[Dict[str, Any]]) -> int:
        """Counts instances where a failing command was re-issued without state changes.

        A command is a repeated failing command if:
        1. Previous command with same tool & arguments failed (exit_code != 0 or error).
        2. No intervening file edit/write tool was called between failures.
        """
        repeated_failing_count = 0
        last_failed_sig: Optional[str] = None
        state_modified_since_failure = False

        for invocation in tool_trace:
            tool_name = invocation.get("tool_name", "")
            args = invocation.get("arguments", {})
            exit_code = invocation.get("exit_code", 0)
            is_error = exit_code != 0 or bool(invocation.get("error"))

            # Signature of the command/invocation
            arg_summary = str(sorted(args.items())) if isinstance(args, dict) else str(args)
            sig = f"{tool_name}:{arg_summary}"

            # Check if this invocation modifies repo state
            if tool_name in ("edit_file", "write_file", "submit_patch"):
                state_modified_since_failure = True
                last_failed_sig = None

            if is_error:
                if sig == last_failed_sig and not state_modified_since_failure:
                    repeated_failing_count += 1
                last_failed_sig = sig
                state_modified_since_failure = False
            else:
                if sig == last_failed_sig:
                    # Successful re-execution or resolved
                    last_failed_sig = None

        return repeated_failing_count

    @staticmethod
    def calculate_tool_invocation_errors(tool_trace: List[Dict[str, Any]]) -> int:
        """Counts tool invocations that resulted in error or non-zero exit code."""
        error_count = 0
        for invocation in tool_trace:
            exit_code = invocation.get("exit_code", 0)
            if exit_code != 0 or bool(invocation.get("error")):
                error_count += 1
        return error_count

    @staticmethod
    def calculate_repeated_commands(tool_trace: List[Dict[str, Any]]) -> int:
        """Counts consecutive duplicate tool calls regardless of outcome."""
        repeated_count = 0
        last_sig: Optional[str] = None

        for invocation in tool_trace:
            tool_name = invocation.get("tool_name", "")
            args = invocation.get("arguments", {})
            arg_summary = str(sorted(args.items())) if isinstance(args, dict) else str(args)
            sig = f"{tool_name}:{arg_summary}"

            if sig == last_sig:
                repeated_count += 1
            last_sig = sig

        return repeated_count

    @classmethod
    def aggregate_task_records(
        cls,
        condition: ConditionType,
        records: List[TaskEvaluationRecord],
        adapter_size_bytes: int = 0,
    ) -> AblationAggregateMetrics:
        """Aggregates individual task evaluation records into condition-level metrics."""
        task_count = len(records)
        if task_count == 0:
            return AblationAggregateMetrics(condition=condition)

        success_count = sum(1 for r in records if r.success)
        total_repeated = sum(r.repeated_command_count for r in records)
        total_repeated_failing = sum(r.repeated_failing_command_count for r in records)
        total_tool_errors = sum(r.tool_invocation_error_count for r in records)
        total_tool_calls = sum(r.tool_calls for r in records)
        total_turns = sum(r.turns for r in records)
        total_runtime = sum(r.runtime_ms for r in records)

        failure_dist: Dict[str, int] = {}
        for r in records:
            if not r.success:
                f_class = r.failure_class or "UNKNOWN"
                failure_dist[f_class] = failure_dist.get(f_class, 0) + 1

        cost_metrics = {
            "adapter_size_bytes": adapter_size_bytes,
            "total_runtime_ms": total_runtime,
            "avg_runtime_ms": total_runtime / task_count,
            "total_tool_calls": total_tool_calls,
            "total_turns": total_turns,
        }

        return AblationAggregateMetrics(
            condition=condition,
            task_count=task_count,
            success_count=success_count,
            pass_rate=success_count / task_count,
            total_repeated_commands=total_repeated,
            repeated_command_rate=total_repeated / total_tool_calls if total_tool_calls > 0 else 0.0,
            total_repeated_failing_commands=total_repeated_failing,
            repeated_failing_command_rate=total_repeated_failing / total_tool_calls if total_tool_calls > 0 else 0.0,
            total_tool_invocation_errors=total_tool_errors,
            tool_invocation_error_rate=total_tool_errors / total_tool_calls if total_tool_calls > 0 else 0.0,
            avg_tool_calls=total_tool_calls / task_count,
            avg_turns=total_turns / task_count,
            avg_runtime_ms=total_runtime / task_count,
            failure_class_distribution=failure_dist,
            cost_metrics=cost_metrics,
        )
