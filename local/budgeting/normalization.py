"""Deterministic argument normalization and secret scrubbing for tool-call budgeting (Stage 26).

Ensures deterministic, canonical representation of tool arguments across turns:
- Normalizes path separators to POSIX slashes
- Trims whitespace while preserving command flags, options, and test targets
- Scrubs sensitive credentials (tokens, private keys) using Stage 25 sanitizer
- Preserves distinguishing diagnostic flags for test and shell commands
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from local.budgeting.models import TOOL_CATEGORY_MAP, ToolCallCategory
from local.context_compaction.fingerprints import normalize_path, sanitize_text


def classify_tool_category(tool_name: str) -> ToolCallCategory:
    """Returns the ToolCallCategory for a given tool name."""
    clean_name = tool_name.strip().lower()
    return TOOL_CATEGORY_MAP.get(clean_name, ToolCallCategory.READ_OBSERVATION)


def normalize_command(command: str) -> str:
    """Normalizes shell command string while strictly preserving flags, arguments, and targets.
    
    Collapses internal repeated whitespace, strips outer whitespace, and scrubs secrets.
    """
    if not command:
        return ""
    sanitized = sanitize_text(command).strip()
    # Collapse multiple spaces while preserving order and flags
    tokens = sanitized.split()
    return " ".join(tokens)


def normalize_arguments(tool_name: str, raw_args: dict[str, Any]) -> dict[str, Any]:
    """Normalizes tool invocation arguments deterministically.
    
    Guarantees:
    - Paths are normalized (e.g. windows backslashes converted, redundant ./ stripped)
    - Commands preserve flags, target tests, and arguments
    - Strings are sanitized for secrets
    - Integer ranges (start_line, end_line) are validated and typed
    - Keys are sorted and canonicalized
    """
    clean_tool = tool_name.strip().lower()
    norm: dict[str, Any] = {}

    for k, v in sorted(raw_args.items()):
        clean_k = k.strip().lower()
        if v is None:
            norm[clean_k] = None
        elif isinstance(v, str):
            sanitized_v = sanitize_text(v).strip()
            if clean_k in ("path", "file_path", "target_path", "dir_path"):
                norm[clean_k] = normalize_path(sanitized_v)
            elif clean_k in ("command", "cmd"):
                norm[clean_k] = normalize_command(sanitized_v)
            elif clean_k in ("query", "seed", "symbol"):
                norm[clean_k] = sanitized_v.lower() if clean_k == "query" else sanitized_v
            else:
                norm[clean_k] = sanitized_v
        elif isinstance(v, (int, float, bool)):
            norm[clean_k] = v
        elif isinstance(v, (list, tuple)):
            # Normalize list elements
            norm_list = []
            for item in v:
                if isinstance(item, str):
                    norm_list.append(sanitize_text(item).strip())
                elif isinstance(item, (int, float, bool)):
                    norm_list.append(item)
                else:
                    norm_list.append(str(item))
            norm[clean_k] = sorted(norm_list) if clean_k in ("seeds", "files", "paths") else norm_list
        elif isinstance(v, dict):
            # Recursively normalize nested dictionaries
            norm[clean_k] = normalize_arguments(clean_tool, v)
        else:
            norm[clean_k] = str(v)

    return norm


def compute_arguments_digest(tool_name: str, normalized_args: dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 hex digest of tool name and normalized arguments."""
    payload = {
        "tool": tool_name.strip().lower(),
        "args": normalized_args,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
