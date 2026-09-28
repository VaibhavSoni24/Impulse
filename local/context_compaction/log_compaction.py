"""Deterministic test-log compaction for Safe Context Compaction (Stage 25).

Parses and compacts test execution outputs, preserving critical diagnostic lines
(exit codes, commands, failing tests, assertions, tracebacks, file:line refs, stderr)
while collapsing boilerplate, passing test noise, and redundant progress counters.
"""

from __future__ import annotations

import re
from typing import Any

from local.context_compaction.fingerprints import sanitize_text
from local.context_compaction.models import CompactedTestLog

# Regex patterns for identifying test runners
PYTEST_SIGNATURES = [
    re.compile(r"pytest", re.IGNORECASE),
    re.compile(r"=+ (?:test session starts|FAILURES|ERRORS|short test summary info) =+"),
    re.compile(r"collected \d+ items"),
]
UNITTEST_SIGNATURES = [
    re.compile(r"python -m unittest", re.IGNORECASE),
    re.compile(r"FAILED \((?:failures=\d+|errors=\d+)\)"),
    re.compile(r"Ran \d+ tests? in \d+\.\d+s"),
]

# Patterns for critical error information that must NEVER be summarized away
FAILING_TEST_PATTERNS = [
    re.compile(r"FAILED\s+([^\s:]+(?:::[^\s:]+)*)"),
    re.compile(r"(?:FAIL|ERROR):\s+([a-zA-Z0-9_]+)\s+\(([^)]+)\)"),
    re.compile(r"_{3,}\s+([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*)\s+_{3,}"),
]

CRITICAL_ERROR_PATTERNS = [
    re.compile(r"^E\s+.*"),
    re.compile(r"^AssertionError:.*"),
    re.compile(r"^[A-Za-z0-9_]+Error:.*"),
    re.compile(r"^[A-Za-z0-9_]+Exception:.*"),
    re.compile(r"FAILED \((?:failures=\d+|errors=\d+).*\)"),
    re.compile(r"^===+ FAILURES ===+"),
    re.compile(r"^===+ ERRORS ===+"),
    re.compile(r"^===+ short test summary info ===+"),
]

TRACEBACK_PATTERNS = [
    re.compile(r"^Traceback \(most recent call last\):"),
    re.compile(r'^\s*File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+([a-zA-Z0-9_<>\.]+))?'),
    re.compile(r"^\s*>\s+.*"),
    re.compile(r"^\s*line\s+\d+,\s+in\s+"),
]

FILE_LINE_REF_PATTERNS = [
    re.compile(r'File\s+"([^"]+)",\s+line\s+(\d+)'),
    re.compile(r'([a-zA-Z0-9_\-\.\/\\\:]+\.py):(\d+):'),
]

PASS_PATTERNS = [
    re.compile(r"^.* PASSED\s*(?:\[\s*\d+%\])?$"),
    re.compile(r"^test_[a-zA-Z0-9_]+(?:\s*\([^)]+\))?\s*\.\.\.\s*ok$"),
    re.compile(r"^\.+$"),
]

BOILERPLATE_PATTERNS = [
    re.compile(r"^=+ test session starts =+"),
    re.compile(r"^platform\s+[a-zA-Z0-9_\-]+.*"),
    re.compile(r"^rootdir:\s+.*"),
    re.compile(r"^plugins:\s+.*"),
    re.compile(r"^collected\s+\d+\s+items"),
    re.compile(r"^----------------------------------------------------------------------$"),
]


def detect_runner(command: str, stdout: str) -> str:
    """Detects test runner from command and output."""
    cmd_lower = command.lower()
    if "pytest" in cmd_lower:
        return "pytest"
    if "unittest" in cmd_lower:
        return "unittest"
    for pat in PYTEST_SIGNATURES:
        if pat.search(stdout):
            return "pytest"
    for pat in UNITTEST_SIGNATURES:
        if pat.search(stdout):
            return "unittest"
    return "generic"


def extract_failing_tests(lines: list[str]) -> list[str]:
    """Extracts unique names of failing tests."""
    failing: list[str] = []
    seen = set()
    for line in lines:
        sline = line.strip()
        for pat in FAILING_TEST_PATTERNS:
            m = pat.search(sline)
            if m:
                test_id = m.group(1)
                if len(m.groups()) > 1 and m.group(2):
                    test_id = f"{m.group(2)}.{test_id}"
                if test_id not in seen:
                    seen.add(test_id)
                    failing.append(test_id)
    return failing


def extract_file_references(lines: list[str]) -> list[str]:
    """Extracts source file and line references from stack trace lines."""
    refs: list[str] = []
    seen = set()
    for line in lines:
        for pat in FILE_LINE_REF_PATTERNS:
            for m in pat.finditer(line):
                ref = f"{m.group(1)}:{m.group(2)}"
                if ref not in seen:
                    seen.add(ref)
                    refs.append(ref)
    return refs


def compact_test_log(
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str = "",
    max_preserved_lines: int = 250,
) -> CompactedTestLog:
    """Deterministically compacts test output while preserving all critical diagnostics.
    
    Guarantees:
    - Never removes an error line or assertion failure.
    - Preserves all traceback frames and file:line references.
    - Preserves failing test names, runner identity, command, and exit code.
    - Collapses passing lines, boilerplate headers, and progress bars.
    """
    clean_stdout = sanitize_text(stdout or "")
    clean_stderr = sanitize_text(stderr or "")
    combined_text = clean_stdout + ("\n--- STDERR ---\n" + clean_stderr if clean_stderr.strip() else "")

    lines = combined_text.splitlines()
    runner = detect_runner(command, clean_stdout)

    # Outcome
    if exit_code == 0:
        outcome = "PASS"
    else:
        # Check if timeout or fail or error
        if "timed out" in combined_text.lower():
            outcome = "TIMEOUT"
        elif "error" in combined_text.lower() and "failed" not in combined_text.lower():
            outcome = "ERROR"
        else:
            outcome = "FAIL"

    failing_tests = extract_failing_tests(lines)
    file_references = extract_file_references(lines)

    # Classify lines
    preserved_chunks: list[str] = []
    error_lines: list[str] = []
    traceback_frames: list[str] = []
    passed_count = 0
    collapsed_count = 0

    in_traceback_or_failure = False

    for line in lines:
        sline = line.strip()

        # Check for passing test lines
        is_pass = any(pat.match(sline) for pat in PASS_PATTERNS)
        if is_pass:
            passed_count += 1
            collapsed_count += 1
            continue

        # Check for setup boilerplate
        is_boilerplate = any(pat.match(sline) for pat in BOILERPLATE_PATTERNS)
        if is_boilerplate:
            collapsed_count += 1
            continue

        # Check for critical errors
        is_critical_error = any(pat.search(sline) for pat in CRITICAL_ERROR_PATTERNS)
        if is_critical_error:
            error_lines.append(sline)
            in_traceback_or_failure = True
            preserved_chunks.append(line)
            continue

        # Check for traceback frames
        is_traceback = any(pat.search(sline) for pat in TRACEBACK_PATTERNS)
        if is_traceback:
            traceback_frames.append(sline)
            in_traceback_or_failure = True
            preserved_chunks.append(line)
            continue

        # If inside a failure block, preserve context
        if in_traceback_or_failure:
            # End failure block if we hit a clean separator or session summary
            if sline.startswith("=== ") and not ("FAILURES" in sline or "ERRORS" in sline):
                in_traceback_or_failure = False
            preserved_chunks.append(line)
        elif exit_code != 0:
            # When command failed, preserve lines that might contain diagnostic context
            if sline:
                preserved_chunks.append(line)

    # Stderr summary if present
    stderr_summary = ""
    if clean_stderr.strip():
        err_lines = [l for l in clean_stderr.splitlines() if l.strip()]
        stderr_summary = "\n".join(err_lines[:15])

    # Assemble preserved text
    out_lines: list[str] = [
        f"COMMAND: {command}",
        f"RUNNER: {runner} | EXIT_CODE: {exit_code} | STATUS: {outcome}",
    ]

    if failing_tests:
        out_lines.append(f"FAILING TESTS ({len(failing_tests)}): {', '.join(failing_tests)}")

    if collapsed_count > 0:
        out_lines.append(f"[{collapsed_count} boilerplate/passing lines collapsed]")

    if outcome == "PASS" and not preserved_chunks:
        out_lines.append("All tests passed successfully.")
    else:
        # Bounded preservation of diagnostic lines
        if len(preserved_chunks) > max_preserved_lines:
            # Explicitly keep all error lines and tracebacks, and slice surrounding context
            guaranteed_critical = set(error_lines + traceback_frames)
            filtered: list[str] = []
            for l in preserved_chunks:
                if l.strip() in guaranteed_critical or len(filtered) < max_preserved_lines:
                    filtered.append(l)
            filtered.append(f"[... {len(preserved_chunks) - len(filtered)} diagnostic context lines truncated; errors preserved ...]")
            out_lines.extend(filtered)
        else:
            out_lines.extend(preserved_chunks)

    final_preserved_text = "\n".join(out_lines)

    return CompactedTestLog(
        command=command,
        exit_code=exit_code,
        runner=runner,
        outcome=outcome,
        failing_tests=failing_tests,
        error_lines=error_lines,
        traceback_frames=traceback_frames,
        file_references=file_references,
        stderr_summary=stderr_summary,
        passed_count=passed_count,
        failed_count=len(failing_tests),
        collapsed_boilerplate_lines=collapsed_count,
        preserved_text=final_preserved_text,
    )
