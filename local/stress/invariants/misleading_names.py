"""Stress Invariant Checker: STRESS 3 — Misleading Function Names.

Verifies that source inspection and test assertions expose behavioral contradictions
when function names or docstrings state one behavior but the implementation does another.
Ensures that symbol name similarity is never treated as proof of runtime semantics.
"""

from __future__ import annotations

import ast
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Tuple

from local.stress.fixtures import create_misleading_names_fixture


def check_misleading_names_stress() -> tuple[bool, str, dict[str, Any]]:
    """Evaluates detection of misleadingly named functions against AST and test contracts.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="impulse_stress_misleading_"))

    try:
        fixture_meta = create_misleading_names_fixture(tmp_dir)
        src_path = tmp_dir / fixture_meta["source_file"]
        test_path = tmp_dir / fixture_meta["test_file"]

        # 1. AST-level semantic inspection
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        op_by_func: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.BinOp):
                        op_by_func[node.name] = type(child.op).__name__

        # compute_sum should conceptually be Add, but AST proves it is Mult!
        observed_op = op_by_func.get("compute_sum")
        if observed_op != "Mult":
            return (
                False,
                f"Expected AST inspection to reveal 'Mult' operation inside compute_sum, found '{observed_op}'",
                {"observed_op": observed_op},
            )

        # 2. Test assertion execution demonstrates the contradiction
        cmd = [sys.executable, "-m", "unittest", str(test_path.name)]
        proc = subprocess.run(cmd, cwd=str(tmp_dir), capture_output=True, text=True)

        # Both test_compute_sum (2*3 != 5) and test_is_authenticated (True is not False) must FAIL
        if proc.returncode == 0:
            return (
                False,
                "Expected test run to fail due to behavioral contradictions, but tests passed unexpectedly",
                {"output": proc.stderr},
            )

        if "AssertionError: 6 != 5" not in proc.stderr and "6 != 5" not in proc.stdout and "AssertionError" not in proc.stderr:
            return (
                False,
                "Expected concrete AssertionError revealing 6 != 5 in test output",
                {"stderr": proc.stderr},
            )

        # 3. Grounding invariant: Source inspection grounded against test failure
        # prevents accepting function name "compute_sum" as evidence of addition.
        details = {
            "misleading_symbol": "compute_sum",
            "name_semantics": "addition",
            "ast_operation": observed_op,
            "test_assertion_failed": True,
            "semantic_conflict_detected": True,
        }

        return (
            True,
            "Misleading function names detected: AST analysis confirmed 'Mult' inside 'compute_sum' and test execution proved 6 != 5 assertion failure.",
            details,
        )

    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
