"""Deterministic, resource-bounded fixture generators for IMPULSE Stress Suite (Stage 46).

All fixtures:
1. Generate synthetic state in isolated temporary directories.
2. Produce deterministic contents with zero external network or GPU dependencies.
3. Clean up temporary state safely.
4. Capture actual sizes, byte counts, and metrics for verifiable reporting.
5. Never consume or borrow locked held-out tasks.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional


def create_synthetic_git_repo(root: Path) -> None:
    """Initializes a minimal hermetic git repository in root."""
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Stress Test Author",
            "GIT_AUTHOR_EMAIL": "stress@impulse.local",
            "GIT_COMMITTER_NAME": "Stress Test Author",
            "GIT_COMMITTER_EMAIL": "stress@impulse.local",
            "LC_ALL": "C",
        }
    )
    subprocess.run(["git", "init"], cwd=str(root), env=env, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Stress Author"], cwd=str(root), env=env, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "stress@impulse.local"], cwd=str(root), env=env, capture_output=True, check=True)


def create_large_repo_fixture(
    target_dir: Path,
    num_files: int = 120,
    depth: int = 3,
) -> dict[str, Any]:
    """Generates a synthetic repository with many files and nested directories.

    Args:
        target_dir: Root directory for the synthetic repository
        num_files: Total number of files to generate (default 120, bounded to <= 1000)
        depth: Directory nesting depth (default 3)

    Returns:
        dict with metadata: file_count, directory_count, total_bytes, relative_paths
    """
    if num_files > 1000:
        raise ValueError(f"num_files must be <= 1000 to maintain resource bounding, got {num_files}")
    if depth < 1 or depth > 10:
        raise ValueError(f"depth must be between 1 and 10, got {depth}")

    target_dir.mkdir(parents=True, exist_ok=True)
    create_synthetic_git_repo(target_dir)

    total_bytes = 0
    created_paths: list[str] = []
    dir_count = 0

    # Create nested directories
    current_dirs = [target_dir]
    for d in range(1, depth + 1):
        next_dirs = []
        for p in current_dirs:
            for branch in ["src", "pkg", "core", "ext"]:
                sub = p / f"level_{d}_{branch}"
                sub.mkdir(parents=True, exist_ok=True)
                next_dirs.append(sub)
                dir_count += 1
        current_dirs = next_dirs

    # Distribute files deterministically
    num_dirs = len(current_dirs)
    for i in range(num_files):
        assigned_dir = current_dirs[i % num_dirs]
        filename = f"module_{i:04d}.py"
        filepath = assigned_dir / filename
        content = (
            f'"""Synthetic stress test module {i:04d}."""\n\n'
            f"def compute_metric_{i:04d}(val: int) -> int:\n"
            f"    return val * {i + 1}\n\n"
            f"CONSTANT_{i:04d} = {i}\n"
        )
        filepath.write_text(content, encoding="utf-8")
        total_bytes += filepath.stat().st_size
        rel = str(filepath.relative_to(target_dir)).replace("\\", "/")
        created_paths.append(rel)

    # Add initial commit
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Stress Author",
            "GIT_AUTHOR_EMAIL": "stress@impulse.local",
            "GIT_COMMITTER_NAME": "Stress Author",
            "GIT_COMMITTER_EMAIL": "stress@impulse.local",
        }
    )
    subprocess.run(["git", "add", "."], cwd=str(target_dir), env=env, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial synthetic large repo"], cwd=str(target_dir), env=env, capture_output=True, check=True)

    return {
        "file_count": num_files,
        "directory_count": dir_count,
        "total_bytes": total_bytes,
        "relative_paths": created_paths,
    }


def create_ambiguous_issue_fixture() -> dict[str, Any]:
    """Generates an ambiguous issue scenario with multiple plausible target symbols."""
    return {
        "issue_id": "SYNTHETIC-STRESS-AMBIGUOUS-001",
        "title": "Date formatting fails under edge cases",
        "description": (
            "The system sometimes outputs incorrect date representations. "
            "Need to ensure that formatting complies with the updated specifications "
            "without breaking legacy callers."
        ),
        "competing_symbols": [
            "core.dates:format_iso",
            "utils.formatting:format_date_custom",
            "legacy.time_utils:render_date_string",
            "api.serializers:serialize_timestamp",
        ],
        "ambiguity_type": "MULTIPLE_PLAUSIBLE_TARGETS",
        "expected_action": "RECONNAISSANCE_BEFORE_EDIT",
    }


def create_misleading_names_fixture(target_dir: Path) -> dict[str, Any]:
    """Generates a repository with misleading symbol names and contradictory tests."""
    target_dir.mkdir(parents=True, exist_ok=True)
    create_synthetic_git_repo(target_dir)

    src_file = target_dir / "calculator.py"
    src_content = (
        '"""Calculator utilities with deceptive symbol names."""\n\n'
        "def compute_sum(a: int, b: int) -> int:\n"
        '    """Returns the sum of two integers."""\n'
        "    # Misleading implementation: actually multiplies!\n"
        "    return a * b\n\n"
        "def is_authenticated(user_token: str) -> bool:\n"
        '    """Verifies user session token."""\n'
        "    # Misleading implementation: always returns True!\n"
        "    return True\n"
    )
    src_file.write_text(src_content, encoding="utf-8")

    test_file = target_dir / "test_calculator.py"
    test_content = (
        "import unittest\n"
        "from calculator import compute_sum, is_authenticated\n\n"
        "class TestCalculator(unittest.TestCase):\n"
        "    def test_compute_sum(self):\n"
        "        # Concrete assertion expects addition 2 + 3 == 5\n"
        "        self.assertEqual(compute_sum(2, 3), 5)\n\n"
        "    def test_is_authenticated(self):\n"
        "        self.assertFalse(is_authenticated('invalid_token'))\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n"
    )
    test_file.write_text(test_content, encoding="utf-8")

    env = os.environ.copy()
    subprocess.run(["git", "add", "."], cwd=str(target_dir), env=env, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial misleading repo"], cwd=str(target_dir), env=env, capture_output=True, check=True)

    return {
        "source_file": "calculator.py",
        "test_file": "test_calculator.py",
        "misleading_symbols": ["compute_sum", "is_authenticated"],
    }


def create_multifile_repo_fixture(target_dir: Path) -> dict[str, Any]:
    """Generates a repository with a caller, implementation, and test module."""
    target_dir.mkdir(parents=True, exist_ok=True)
    create_synthetic_git_repo(target_dir)

    service_file = target_dir / "service.py"
    service_content = (
        '"""Core service module."""\n\n'
        "def execute_task(val: int) -> int:\n"
        "    return val + 10\n"
    )
    service_file.write_text(service_content, encoding="utf-8")

    client_file = target_dir / "client.py"
    client_content = (
        '"""Client calling core service."""\n\n'
        "from service import execute_task\n\n"
        "def client_run(x: int) -> int:\n"
        "    return execute_task(x) * 2\n"
    )
    client_file.write_text(client_content, encoding="utf-8")

    test_file = target_dir / "test_pipeline.py"
    test_content = (
        "import unittest\n"
        "from client import client_run\n\n"
        "class TestPipeline(unittest.TestCase):\n"
        "    def test_run(self):\n"
        "        self.assertEqual(client_run(5), 30)\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n"
    )
    test_file.write_text(test_content, encoding="utf-8")

    env = os.environ.copy()
    subprocess.run(["git", "add", "."], cwd=str(target_dir), env=env, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Baseline multi-file project"], cwd=str(target_dir), env=env, capture_output=True, check=True)

    return {
        "files": ["service.py", "client.py", "test_pipeline.py"],
        "target_dir": target_dir,
    }


def create_hidden_dependency_fixture() -> dict[str, Any]:
    """Generates an explicit dependency graph with indirect/hidden relationships."""
    nodes = {
        "entrypoint": {"type": "function", "file": "app.py", "line": 10},
        "dispatcher": {"type": "class", "file": "core/dispatch.py", "line": 25},
        "registry": {"type": "dict", "file": "core/registry.py", "line": 15},
        "hidden_handler": {"type": "function", "file": "handlers/secure.py", "line": 50},
        "unrelated_node_1": {"type": "function", "file": "misc/log.py", "line": 5},
        "unrelated_node_2": {"type": "function", "file": "misc/cache.py", "line": 8},
    }
    # entrypoint -> dispatcher -> registry -> hidden_handler (indirect)
    edges = [
        {"from": "entrypoint", "to": "dispatcher", "kind": "calls"},
        {"from": "dispatcher", "to": "registry", "kind": "queries"},
        {"from": "registry", "to": "hidden_handler", "kind": "resolves_dynamically"},
        {"from": "entrypoint", "to": "unrelated_node_1", "kind": "calls"},
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "target_symbol": "entrypoint",
        "hidden_dependency": "hidden_handler",
    }


def create_long_log_fixture(target_dir: Path, total_bytes: int = 50_000) -> Path:
    """Generates a deterministic verbose test log with identifiable error and summary."""
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / "verbose_test_run.log"

    header = (
        "=== TEST SUITE EXECUTION START ===\n"
        "Running 450 tests across 18 packages...\n"
    )
    error_trace = (
        "\n--- FAILURE TRACE START ---\n"
        "Traceback (most recent call last):\n"
        '  File "pkg/processor.py", line 142, in process_batch\n'
        "    raise KeyError('missing_mandatory_batch_header')\n"
        "KeyError: 'missing_mandatory_batch_header'\n"
        "--- FAILURE TRACE END ---\n\n"
    )
    summary = (
        "\n=== TEST SUITE EXECUTION SUMMARY ===\n"
        "FAILED (failures=1, errors=0, skipped=4, passed=445)\n"
        "Total time: 48.2s\n"
    )

    content_parts = [header, error_trace]
    current_size = len("".join(content_parts).encode("utf-8")) + len(summary.encode("utf-8"))

    line_idx = 1
    filler_line_template = "INFO [worker-{:02d}] Finished subtask {:05d} status OK in 0.002s\n"
    while current_size < total_bytes:
        line = filler_line_template.format(line_idx % 8, line_idx)
        content_parts.append(line)
        current_size += len(line.encode("utf-8"))
        line_idx += 1

    content_parts.append(summary)
    full_text = "".join(content_parts)
    log_path.write_text(full_text, encoding="utf-8")
    return log_path


def create_preexisting_failure_fixture(target_dir: Path) -> dict[str, Any]:
    """Generates a test project containing a known pre-existing failing test."""
    target_dir.mkdir(parents=True, exist_ok=True)
    create_synthetic_git_repo(target_dir)

    code_file = target_dir / "calculator.py"
    code_content = (
        "def target_func(x: int) -> int:\n"
        "    # Defect to be fixed: off by one\n"
        "    return x + 2\n\n"
        "def legacy_buggy_func() -> int:\n"
        "    # Pre-existing bug\n"
        "    return 42 // 0\n"
    )
    code_file.write_text(code_content, encoding="utf-8")

    test_file = target_dir / "test_calc.py"
    test_content = (
        "import unittest\n"
        "from calculator import target_func, legacy_buggy_func\n\n"
        "class TestCalc(unittest.TestCase):\n"
        "    def test_preexisting_legacy(self):\n"
        "        # Fails in baseline commit\n"
        "        self.assertEqual(legacy_buggy_func(), 42)\n\n"
        "    def test_target_func(self):\n"
        "        # Expected target test\n"
        "        self.assertEqual(target_func(10), 11)\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n"
    )
    test_file.write_text(test_content, encoding="utf-8")

    env = os.environ.copy()
    subprocess.run(["git", "add", "."], cwd=str(target_dir), env=env, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Baseline with pre-existing failure"], cwd=str(target_dir), env=env, capture_output=True, check=True)

    return {
        "preexisting_test": "test_preexisting_legacy",
        "target_test": "test_target_func",
        "target_dir": target_dir,
    }


def create_required_new_file_fixture(target_dir: Path) -> dict[str, Any]:
    """Generates a repository where the fix requires adding a brand new file."""
    target_dir.mkdir(parents=True, exist_ok=True)
    create_synthetic_git_repo(target_dir)

    main_file = target_dir / "main.py"
    main_content = (
        "def run_pipeline(data: str) -> str:\n"
        "    # Will require importing from a new module 'serializer.py'\n"
        "    return data.strip()\n"
    )
    main_file.write_text(main_content, encoding="utf-8")

    test_file = target_dir / "test_main.py"
    test_content = (
        "import unittest\n"
        "from main import run_pipeline\n\n"
        "class TestMain(unittest.TestCase):\n"
        "    def test_run(self):\n"
        "        self.assertEqual(run_pipeline('  test  '), 'test')\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n"
    )
    test_file.write_text(test_content, encoding="utf-8")

    env = os.environ.copy()
    subprocess.run(["git", "add", "."], cwd=str(target_dir), env=env, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Baseline before new file requirement"], cwd=str(target_dir), env=env, capture_output=True, check=True)

    return {
        "new_file_name": "serializer.py",
        "target_dir": target_dir,
    }


def create_binary_file_fixture(target_dir: Path, filename: str = "asset.bin") -> Path:
    """Generates a small deterministic binary file with null and non-UTF-8 bytes."""
    target_dir.mkdir(parents=True, exist_ok=True)
    binary_path = target_dir / filename
    # Deterministic 128 bytes with null bytes and invalid UTF-8 byte sequences
    raw_bytes = bytes([0, 255, 254, 128, 192, 0, 1, 2] * 16)
    binary_path.write_bytes(raw_bytes)
    return binary_path
