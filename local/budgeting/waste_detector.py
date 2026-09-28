"""Wasteful tool call detection and classification (Stage 26).

Identifies repeated and redundant calls under unchanged repository state:
- Exact duplicate file reads
- Unchanged directory/status queries
- Identical semantic queries
- Identical graph lookups
- Repeated test executions without intervening source edits
- Distinguishes SAFE_REDUNDANT from NECESSARY_REPEAT (reruns after edits, retries)
"""

from __future__ import annotations

from typing import Any

from local.budgeting.models import ToolCallCategory, WasteClassification
from local.budgeting.normalization import (
    classify_tool_category,
    compute_arguments_digest,
    normalize_arguments,
)


class WasteDetector:
    """Detects and classifies potentially wasteful or redundant tool invocations.
    
    Safety rule:
    Defaults to UNKNOWN when uncertain to avoid falsely penalizing legitimate retries.
    """

    def __init__(self) -> None:
        # Map: (tool_name, args_digest, repo_state_id) -> call count
        self._state_call_counts: dict[tuple[str, str, str], int] = {}
        # Track last executed commands: normalized_cmd -> repo_state_id
        self._command_history: dict[str, str] = {}
        # Set of files modified since beginning of task run
        self._modified_files: set[str] = set()

    def record_mutation(self, path: str) -> None:
        """Notifies the detector that a source file was mutated."""
        self._modified_files.add(path.strip().replace("\\", "/"))

    def classify_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        repository_state_id: str,
        is_retry: bool = False,
        had_transient_error: bool = False,
        after_mutation: bool = False,
    ) -> WasteClassification:
        """Classifies whether an upcoming tool invocation is redundant or necessary.
        
        Returns:
            WasteClassification (SAFE_REDUNDANT, POSSIBLY_REDUNDANT, NECESSARY_REPEAT, UNKNOWN)
        """
        clean_tool = tool_name.strip().lower()
        category = classify_tool_category(clean_tool)
        norm_args = normalize_arguments(clean_tool, arguments)
        args_digest = compute_arguments_digest(clean_tool, norm_args)
        state_key = (clean_tool, args_digest, repository_state_id)

        prior_count = self._state_call_counts.get(state_key, 0)
        self._state_call_counts[state_key] = prior_count + 1

        # 1. Legitimate repetitions (after edit or transient retry)
        if after_mutation or is_retry or had_transient_error:
            return WasteClassification.NECESSARY_REPEAT

        # 2. First execution in this state is never redundant
        if prior_count == 0:
            if clean_tool == "run_command":
                cmd = norm_args.get("command", "")
                self._command_history[cmd] = repository_state_id
            return WasteClassification.UNKNOWN

        # 3. Read and observation tools on unchanged repository state
        if category == ToolCallCategory.READ_OBSERVATION:
            # Exact same query under exact same repository state
            return WasteClassification.SAFE_REDUNDANT

        # 4. Command executions (run_command)
        if category == ToolCallCategory.EXECUTION:
            cmd = norm_args.get("command", "")
            prev_repo_state = self._command_history.get(cmd)
            self._command_history[cmd] = repository_state_id

            if prev_repo_state == repository_state_id:
                # Repeated test or build command without any intervening repository edit
                return WasteClassification.POSSIBLY_REDUNDANT
            else:
                return WasteClassification.NECESSARY_REPEAT

        # 5. Mutations and submissions are never marked safe-redundant
        if category in (ToolCallCategory.MUTATION, ToolCallCategory.SUBMISSION):
            return WasteClassification.UNKNOWN

        return WasteClassification.UNKNOWN
