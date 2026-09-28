"""Safety and Information-Preservation Policy for Context Compaction (Stage 25).

Implements explicit rule-based classification of compaction actions:
- SAFE_TO_COMPACT: Redundant, identical, or non-diagnostic output safe to collapse
- PRESERVE_EXACTLY: Critical diagnostic evidence, diffs, stack traces, security findings
- PRESERVE_WITH_STRUCTURE: Test logs, modified files, structured facts
- UNKNOWN: Default state that MUST trigger preservation

Hard Safety Rule:
When uncertain, the policy ALWAYS mandates PRESERVE (never compact).
"""

from __future__ import annotations

import re
from typing import Any

from local.context_compaction.models import CompactionAction, ObservationType

# Signatures that mandate exact preservation
CRITICAL_PRESERVE_SIGNATURES = [
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"AssertionError:"),
    re.compile(r"SyntaxError:"),
    re.compile(r"IndentationError:"),
    re.compile(r"NameError:"),
    re.compile(r"TypeError:"),
    re.compile(r"AttributeError:"),
    re.compile(r"ImportError:"),
    re.compile(r"ModuleNotFoundError:"),
    re.compile(r"Segmentation fault"),
    re.compile(r"Fatal error:"),
    re.compile(r"Compilation failed"),
]

# Patterns representing safe-to-compact directory listings
DIRECTORY_LISTING_PATTERNS = [
    re.compile(r"^(?:ls|dir|find|tree)\b"),
    re.compile(r"(?:total \d+|\b[d\-][rwx\-]{9}\b)"),
]


class CompactionPolicy:
    """Enforces safety invariants for all compaction candidates."""

    @classmethod
    def evaluate(
        cls,
        obs_type: ObservationType,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> CompactionAction:
        """Evaluates whether an observation is safe to compact or must be preserved.
        
        When in doubt, returns PRESERVE_EXACTLY.
        """
        meta = metadata or {}
        content_str = content or ""

        # 1. Critical signals that demand exact preservation
        if meta.get("security_finding") or meta.get("under_review") or meta.get("is_diff"):
            return CompactionAction.PRESERVE_EXACTLY

        if meta.get("exit_code") is not None and meta["exit_code"] != 0:
            # Failed commands require structured or exact preservation
            return CompactionAction.PRESERVE_WITH_STRUCTURE

        for sig in CRITICAL_PRESERVE_SIGNATURES:
            if sig.search(content_str):
                return CompactionAction.PRESERVE_EXACTLY

        # 2. Domain-specific rules
        if obs_type == ObservationType.TEST_LOG:
            # If test log has non-zero exit code or failing tests, preserve with structure
            if meta.get("exit_code", 0) != 0 or meta.get("failed_count", 0) > 0:
                return CompactionAction.PRESERVE_WITH_STRUCTURE
            # Clean, repeated test run
            if meta.get("is_duplicate"):
                return CompactionAction.SAFE_TO_COMPACT
            return CompactionAction.PRESERVE_WITH_STRUCTURE

        if obs_type == ObservationType.FILE_READ:
            # If the file content is proven identical by fingerprint
            if meta.get("is_unchanged"):
                return CompactionAction.SAFE_TO_COMPACT
            # If new or modified, preserve structure
            return CompactionAction.PRESERVE_WITH_STRUCTURE

        if obs_type == ObservationType.REPOSITORY_FACT:
            if meta.get("is_duplicate"):
                return CompactionAction.SAFE_TO_COMPACT
            return CompactionAction.PRESERVE_WITH_STRUCTURE

        if obs_type == ObservationType.COMMAND_OUTPUT:
            # Check for directory listing
            cmd = meta.get("command", "")
            is_dir_list = any(p.search(cmd) or p.search(content_str) for p in DIRECTORY_LISTING_PATTERNS)
            if is_dir_list and meta.get("is_duplicate"):
                return CompactionAction.SAFE_TO_COMPACT
            if meta.get("is_duplicate") and meta.get("exit_code") == 0:
                return CompactionAction.SAFE_TO_COMPACT

        # 3. Default fallback: When uncertain, PRESERVE
        return CompactionAction.PRESERVE_EXACTLY

    @classmethod
    def is_safe_to_compact(cls, action: CompactionAction) -> bool:
        """Determines if the action allows lossy or collapsed compaction."""
        return action == CompactionAction.SAFE_TO_COMPACT
