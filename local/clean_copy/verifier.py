"""Post-application task verification subsystem for Clean-Copy Evaluation (Stage 28 Phase 12).

Executes tests or validation commands strictly inside the clean validation workspace
AFTER successful patch application.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time
from typing import Optional

from local.runner.models import TaskRecord


@dataclass
class VerificationResult:
    """Outcome of running verification inside the clean validation workspace."""

    command: str
    exit_code: int
    passed: bool
    stdout: str
    stderr: str
    elapsed_seconds: float
    error_message: Optional[str] = None


class CleanCopyVerifier:
    """Executes deterministic task verification in the clean validation workspace."""

    def __init__(self, default_timeout: int = 60) -> None:
        self.default_timeout = default_timeout

    def determine_command(
        self,
        workspace_root: Path,
        task: TaskRecord,
        custom_command: Optional[str] = None,
    ) -> str:
        """Determines the authoritative verification command."""
        if custom_command:
            return custom_command

        # Check for pytest.ini or tests/ directory
        if (workspace_root / "pytest.ini").exists() or (workspace_root / "tests").is_dir():
            return "pytest -q"

        return "python -m unittest discover tests"

    def verify(
        self,
        workspace_root: Path,
        task: TaskRecord,
        custom_command: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> VerificationResult:
        """Executes verification command inside workspace_root."""
        cmd = self.determine_command(workspace_root, task, custom_command)
        timeout_sec = timeout or self.default_timeout

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["LC_ALL"] = "C"

        start_t = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(workspace_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            elapsed = time.perf_counter() - start_t
            passed = res.returncode == 0
            return VerificationResult(
                command=cmd,
                exit_code=res.returncode,
                passed=passed,
                stdout=res.stdout[:50_000],  # bound log size
                stderr=res.stderr[:50_000],
                elapsed_seconds=round(elapsed, 4),
                error_message=None if passed else f"Verification failed with exit code {res.returncode}",
            )
        except subprocess.TimeoutExpired as e:
            elapsed = time.perf_counter() - start_t
            return VerificationResult(
                command=cmd,
                exit_code=-1,
                passed=False,
                stdout=e.stdout[:10_000] if e.stdout else "",
                stderr=e.stderr[:10_000] if e.stderr else "Timeout expired",
                elapsed_seconds=round(elapsed, 4),
                error_message=f"Verification timed out after {timeout_sec}s",
            )
        except Exception as e:
            elapsed = time.perf_counter() - start_t
            return VerificationResult(
                command=cmd,
                exit_code=-1,
                passed=False,
                stdout="",
                stderr=str(e),
                elapsed_seconds=round(elapsed, 4),
                error_message=f"Verification command execution error: {e}",
            )
