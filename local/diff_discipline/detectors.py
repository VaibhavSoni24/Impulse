"""Detectors for scratch files, logs, debug statements, local config, machine paths, and secrets.

Stage 27 Final Diff Discipline detectors.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from local.context_compaction.fingerprints import (
    KEY_VAL_SECRET_PATTERN,
    PRIVATE_KEY_PATTERN,
    TOKEN_SECRET_PATTERN,
    normalize_path,
)
from local.diff_discipline.models import (
    ArtifactClass,
    ArtifactFinding,
    HygieneAction,
)

# Common scratch patterns
SCRATCH_FILENAME_PATTERNS = [
    re.compile(r"^scratch.*\.py$", re.IGNORECASE),
    re.compile(r"^tmp_.*\.py$", re.IGNORECASE),
    re.compile(r"^temp_.*\.py$", re.IGNORECASE),
    re.compile(r"^debug_.*\.py$", re.IGNORECASE),
    re.compile(r"^test_tmp.*(?:\.py|\.txt|\.json)?$", re.IGNORECASE),
    re.compile(r"^tmp_output.*$", re.IGNORECASE),
    re.compile(r"^out\.txt$", re.IGNORECASE),
    re.compile(r".*\.(?:bak|tmp|orig|rej|swp|swo|dump)$", re.IGNORECASE),
    re.compile(r"^#.*#$"),
    re.compile(r".*~$"),
]

# Temporary patch file patterns (not legitimate repo diffs/manifests)
TEMPORARY_PATCH_PATTERNS = [
    re.compile(r"^temp(?:_\w+)?\.patch$", re.IGNORECASE),
    re.compile(r"^tmp(?:_\w+)?\.patch$", re.IGNORECASE),
    re.compile(r"^patch_\d+\.diff$", re.IGNORECASE),
    re.compile(r"^diff_dump.*\.txt$", re.IGNORECASE),
]

# Log file patterns
LOG_FILENAME_PATTERNS = [
    re.compile(r".*\.log$", re.IGNORECASE),
    re.compile(r".*\.trace$", re.IGNORECASE),
    re.compile(r"^server\.log$", re.IGNORECASE),
    re.compile(r"^run\.log$", re.IGNORECASE),
    re.compile(r"^test_execution\.log$", re.IGNORECASE),
]

# Local configuration patterns
LOCAL_CONFIG_PATTERNS = [
    re.compile(r"^\.env(?:\.local|\.dev|\.prod|\.test)?$", re.IGNORECASE),
    re.compile(r"^secrets\.json$", re.IGNORECASE),
    re.compile(r"^credentials\.json$", re.IGNORECASE),
    re.compile(r"^local_settings\.py$", re.IGNORECASE),
    re.compile(r"^config\.local\.json$", re.IGNORECASE),
]

# Machine-specific directory patterns
MACHINE_DIR_PATTERNS = [
    re.compile(r"(?:^|/)__pycache__(?:/|$)"),
    re.compile(r"(?:^|/)\.pytest_cache(?:/|$)"),
    re.compile(r"(?:^|/)\.mypy_cache(?:/|$)"),
    re.compile(r"(?:^|/)\.ruff_cache(?:/|$)"),
    re.compile(r"(?:^|/)\.vscode(?:/|$)"),
    re.compile(r"(?:^|/)\.idea(?:/|$)"),
    re.compile(r"(?:^|/)\.venv(?:/|$)"),
    re.compile(r"(?:^|/)venv(?:/|$)"),
]

# Source-level debug marker patterns
DEBUG_SOURCE_PATTERNS = [
    (re.compile(r"\bbreakpoint\(\)"), "breakpoint() invocation"),
    (re.compile(r"\bpdb\.set_trace\(\)"), "pdb.set_trace() invocation"),
    (re.compile(r"\bimport\s+pdb\b"), "pdb import"),
    (re.compile(r"\bpdb\.post_mortem\(\)"), "pdb.post_mortem() invocation"),
    (re.compile(r"^\s*print\(\s*['\"](?:DEBUG|TEMP|TODO_REMOVE|XXX)", re.MULTILINE), "temporary debug print"),
    (re.compile(r"^\s*console\.log\(\s*['\"](?:DEBUG|TEMP|TODO_REMOVE)", re.MULTILINE), "temporary console.log"),
]

# Machine-specific absolute path patterns in content
MACHINE_PATH_PATTERNS = [
    re.compile(r"\b[a-zA-Z]:\\(?:Users|Documents and Settings)\\[a-zA-Z0-9_\-\\]+"),
    re.compile(r"\b/(?:home|Users)/[a-zA-Z0-9_\-]+/(?!$)"),
]

# Secret patterns for content scanning
SECRET_SCAN_PATTERNS = [
    (KEY_VAL_SECRET_PATTERN, "key-value credential"),
    (TOKEN_SECRET_PATTERN, "access token"),
    (PRIVATE_KEY_PATTERN, "private key header"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS Access Key ID"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), "OpenAI API Key"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), "Google API Key"),
]


def detect_scratch_file(
    path: str,
    is_tracked: bool = False,
    is_referenced: bool = False,
) -> Optional[ArtifactFinding]:
    """Detects whether a file matches scratch/temporary development patterns.
    
    Preserves:
    - legitimate test fixtures (e.g. tests/fixtures/*)
    - benchmark files
    - documentation
    - referenced files
    """
    norm = normalize_path(path)
    file_name = Path(norm).name

    # Never treat files in tests/fixtures as scratch
    if norm.startswith("tests/fixtures/"):
        return None

    # Never treat experiment reports or manifests as scratch
    if norm.startswith("experiments/") and (norm.endswith(".md") or norm.endswith(".json") or norm.endswith(".yaml") or norm.endswith(".yml")):
        return None

    # Check scratch filename patterns
    matched_pattern = False
    for pat in SCRATCH_FILENAME_PATTERNS:
        if pat.match(file_name):
            matched_pattern = True
            break

    if not matched_pattern:
        for pat in TEMPORARY_PATCH_PATTERNS:
            if pat.match(file_name):
                matched_pattern = True
                break

    if not matched_pattern:
        return None

    # If the file is referenced anywhere in the repository, do not auto-remove!
    if is_referenced:
        return ArtifactFinding(
            path=norm,
            artifact_class=ArtifactClass.SCRATCH_ARTIFACT,
            recommended_action=HygieneAction.REVIEW,
            reason=f"File '{file_name}' matches scratch pattern but is referenced in repository.",
            confidence=0.8,
            is_tracked=is_tracked,
            is_referenced=True,
            details={"pattern_matched": file_name},
        )

    # Tracked scratch files require review before deletion to prevent unexpected git diffs
    if is_tracked:
        return ArtifactFinding(
            path=norm,
            artifact_class=ArtifactClass.SCRATCH_ARTIFACT,
            recommended_action=HygieneAction.REVIEW,
            reason=f"File '{file_name}' matches scratch pattern and is tracked in Git.",
            confidence=0.9,
            is_tracked=True,
            is_referenced=False,
            details={"pattern_matched": file_name},
        )

    # Untracked, unreferenced scratch file -> safely removable
    return ArtifactFinding(
        path=norm,
        artifact_class=ArtifactClass.SCRATCH_ARTIFACT,
        recommended_action=HygieneAction.REMOVE,
        reason=f"File '{file_name}' is an untracked, unreferenced scratch artifact.",
        confidence=0.95,
        is_tracked=False,
        is_referenced=False,
        details={"pattern_matched": file_name},
    )


def detect_log_file(
    path: str,
    is_tracked: bool = False,
    is_referenced: bool = False,
) -> Optional[ArtifactFinding]:
    """Detects local execution logs and traces."""
    norm = normalize_path(path)
    file_name = Path(norm).name

    # Experiment reports and benchmark manifests are not disposable logs
    if norm.startswith("experiments/") or norm.startswith("benchmark/"):
        return None

    matched = False
    for pat in LOG_FILENAME_PATTERNS:
        if pat.match(file_name):
            matched = True
            break

    if not matched:
        return None

    if is_referenced:
        return ArtifactFinding(
            path=norm,
            artifact_class=ArtifactClass.IGNORED_LOCAL_ARTIFACT,
            recommended_action=HygieneAction.REVIEW,
            reason=f"Log file '{file_name}' is referenced in codebase.",
            confidence=0.8,
            is_tracked=is_tracked,
            is_referenced=True,
        )

    if is_tracked:
        return ArtifactFinding(
            path=norm,
            artifact_class=ArtifactClass.DEBUG_ARTIFACT,
            recommended_action=HygieneAction.REVIEW,
            reason=f"Log file '{file_name}' is tracked in Git.",
            confidence=0.9,
            is_tracked=True,
            is_referenced=False,
        )

    return ArtifactFinding(
        path=norm,
        artifact_class=ArtifactClass.IGNORED_LOCAL_ARTIFACT,
        recommended_action=HygieneAction.REMOVE,
        reason=f"Untracked local log file '{file_name}'.",
        confidence=0.95,
        is_tracked=False,
        is_referenced=False,
    )


def detect_local_config(
    path: str,
    is_tracked: bool = False,
) -> Optional[ArtifactFinding]:
    """Detects local configuration and credential files."""
    norm = normalize_path(path)
    file_name = Path(norm).name

    # .env.example is legitimate required configuration documentation!
    if file_name in (".env.example", ".env.template", ".env.sample"):
        return ArtifactFinding(
            path=norm,
            artifact_class=ArtifactClass.REQUIRED_CONFIG,
            recommended_action=HygieneAction.KEEP,
            reason=f"Example configuration template '{file_name}'.",
            confidence=1.0,
            is_tracked=is_tracked,
            is_referenced=False,
        )

    matched = False
    for pat in LOCAL_CONFIG_PATTERNS:
        if pat.match(file_name):
            matched = True
            break

    if not matched:
        return None

    if is_tracked:
        return ArtifactFinding(
            path=norm,
            artifact_class=ArtifactClass.SECRET_OR_CREDENTIAL,
            recommended_action=HygieneAction.REVIEW,
            reason=f"Local configuration/credential file '{file_name}' is tracked in Git.",
            confidence=0.95,
            is_tracked=True,
            is_referenced=False,
        )

    return ArtifactFinding(
        path=norm,
        artifact_class=ArtifactClass.IGNORED_LOCAL_ARTIFACT,
        recommended_action=HygieneAction.REVIEW,
        reason=f"Untracked local configuration file '{file_name}'.",
        confidence=0.9,
        is_tracked=False,
        is_referenced=False,
    )


def detect_machine_specific(
    path: str,
    is_tracked: bool = False,
) -> Optional[ArtifactFinding]:
    """Detects machine-specific cache directories and bytecode artifacts."""
    norm = normalize_path(path)

    for pat in MACHINE_DIR_PATTERNS:
        if pat.search(norm):
            return ArtifactFinding(
                path=norm,
                artifact_class=ArtifactClass.MACHINE_SPECIFIC_ARTIFACT,
                recommended_action=HygieneAction.REMOVE if not is_tracked else HygieneAction.REVIEW,
                reason=f"Machine-specific build/cache artifact in '{norm}'.",
                confidence=0.98,
                is_tracked=is_tracked,
                is_referenced=False,
            )

    if norm.endswith(".pyc") or norm.endswith(".pyo"):
        return ArtifactFinding(
            path=norm,
            artifact_class=ArtifactClass.MACHINE_SPECIFIC_ARTIFACT,
            recommended_action=HygieneAction.REMOVE if not is_tracked else HygieneAction.REVIEW,
            reason="Compiled Python bytecode.",
            confidence=1.0,
            is_tracked=is_tracked,
            is_referenced=False,
        )

    return None


def scan_content_for_debug_markers(
    path: str,
    content: str,
    is_tracked: bool = False,
) -> list[ArtifactFinding]:
    """Scans text content for temporary debug markers (breakpoint, pdb, temporary print)."""
    norm = normalize_path(path)
    findings: list[ArtifactFinding] = []

    # Skip binary files or non-code/script files
    if not (norm.endswith(".py") or norm.endswith(".sh") or norm.endswith(".js")):
        return findings

    # In tests, print statements are often part of test diagnostics, but breakpoint() or pdb are not
    is_test_file = norm.startswith("tests/") or "/tests/" in norm or Path(norm).name.startswith("test_")

    for line_idx, line in enumerate(content.splitlines(), start=1):
        if is_test_file and ("content =" in line or "content.splitlines" in line or "assert" in line or "def test_" in line or '"""' in line or "'''" in line):
            continue
        for pattern, desc in DEBUG_SOURCE_PATTERNS:
            if pattern.search(line):
                # Allow prints in test files or CLI tools unless marked DEBUG/TEMP
                if "print" in desc and is_test_file and not ("DEBUG" in line or "TEMP" in line or "XXX" in line):
                    continue
                action = HygieneAction.REVIEW
                findings.append(
                    ArtifactFinding(
                        path=norm,
                        artifact_class=ArtifactClass.DEBUG_ARTIFACT,
                        recommended_action=action,
                        reason=f"Line {line_idx}: {desc} detected.",
                        confidence=0.95 if "breakpoint" in desc or "pdb" in desc else 0.85,
                        is_tracked=is_tracked,
                        is_referenced=False,
                        details={
                            "line_number": line_idx,
                            "snippet": line.strip()[:100],
                            "marker_type": desc,
                        },
                    )
                )

    return findings


def scan_content_for_machine_paths(
    path: str,
    content: str,
    is_tracked: bool = False,
) -> list[ArtifactFinding]:
    """Scans content for hardcoded machine-specific absolute file paths."""
    norm = normalize_path(path)
    findings: list[ArtifactFinding] = []

    # Markdown docs may contain illustrative example paths; inspect with lower confidence / review
    is_doc = norm.endswith(".md") or norm.endswith(".rst")

    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern in MACHINE_PATH_PATTERNS:
            if pattern.search(line):
                findings.append(
                    ArtifactFinding(
                        path=norm,
                        artifact_class=ArtifactClass.MACHINE_SPECIFIC_ARTIFACT,
                        recommended_action=HygieneAction.REVIEW,
                        reason=f"Line {line_idx}: Hardcoded absolute machine-specific path detected.",
                        confidence=0.6 if is_doc else 0.9,
                        is_tracked=is_tracked,
                        is_referenced=False,
                        details={
                            "line_number": line_idx,
                            "snippet": line.strip()[:100],
                        },
                    )
                )
    return findings


def scan_content_for_secrets(
    path: str,
    content: str,
    is_tracked: bool = False,
) -> list[ArtifactFinding]:
    """Scans content for credentials or sensitive tokens.
    
    SECURITY RULE:
    Never include the secret value in the finding, reason, or details!
    """
    norm = normalize_path(path)
    findings: list[ArtifactFinding] = []

    is_test_file = norm.startswith("tests/") or Path(norm).name.startswith("test_")

    for line_idx, line in enumerate(content.splitlines(), start=1):
        # Skip regex definitions or test harness fixtures
        if "re.compile" in line or "KEY_VAL_SECRET_PATTERN" in line or "TOKEN_SECRET_PATTERN" in line:
            continue
        if "for secret_pattern in" in line or "secret_pattern," in line or '["token", "secret"' in line:
            continue
        if is_test_file and ("secret" in line.lower() or "token" in line.lower() or "key" in line.lower() or "content" in line.lower()):
            continue

        for pattern, name in SECRET_SCAN_PATTERNS:
            if pattern.search(line):
                findings.append(
                    ArtifactFinding(
                        path=norm,
                        artifact_class=ArtifactClass.SECRET_OR_CREDENTIAL,
                        recommended_action=HygieneAction.REVIEW,
                        reason=f"Line {line_idx}: Potential {name} detected [SECRET_DETECTED_IN_PATH].",
                        confidence=0.9,
                        is_tracked=is_tracked,
                        is_referenced=False,
                        details={
                            "line_number": line_idx,
                            "finding_code": "SECRET_DETECTED_IN_PATH",
                            "credential_type": name,
                        },
                    )
                )
                break  # Only one secret finding per line

    return findings
