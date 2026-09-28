"""Clean repository snapshot management for Stage 28.

Provides CleanRepositorySnapshot and SnapshotManager to guarantee:
- Source revision / commit identity
- Isolated filesystem location
- Clean initial Git state
- No contamination from previous task runs or developer working tree
- Safe disposal after evidence capture
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from typing import Optional

from local.context_compaction.fingerprints import normalize_path
from local.clean_copy.models import WorkspaceCreationMethod

STANDARD_GIT_EXCLUDE = """__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
build/
dist/
.coverage
"""


def _remove_readonly(func, path, excinfo):
    """Error handler for shutil.rmtree on Windows read-only git files."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


class CleanRepositorySnapshot:
    """Represents an isolated clean repository workspace."""

    def __init__(
        self,
        workspace_dir: Path,
        baseline_commit: str,
        task_id: str,
        run_id: str,
        role: str,  # 'agent' or 'validation'
        creation_method: WorkspaceCreationMethod,
        source_repo: Path,
        exclude_file: Optional[Path] = None,
    ) -> None:
        self.workspace_dir = workspace_dir
        self.baseline_commit = baseline_commit
        self.task_id = task_id
        self.run_id = run_id
        self.role = role
        self.creation_method = creation_method
        self.source_repo = source_repo
        self.exclude_file = exclude_file

    def run_git(
        self,
        args: list[str],
        check: bool = True,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Runs a Git command inside the isolated workspace."""
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": "Impulse Evaluator",
                "GIT_AUTHOR_EMAIL": "evaluator@impulse.local",
                "GIT_COMMITTER_NAME": "Impulse Evaluator",
                "GIT_COMMITTER_EMAIL": "evaluator@impulse.local",
                "LC_ALL": "C",
            }
        )
        cmd: list[str] = ["git"]
        if self.exclude_file and self.exclude_file.exists():
            clean_exclude = str(self.exclude_file.resolve()).replace("\\", "/")
            cmd.extend(["-c", f"core.excludesFile={clean_exclude}"])
        cmd.extend(args)
        return subprocess.run(
            cmd,
            cwd=str(self.workspace_dir),
            env=env,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
        )

    def is_clean(self) -> bool:
        """Returns True if the workspace working tree is completely clean."""
        res = self.run_git(["status", "--short"], check=False)
        return len(res.stdout.strip()) == 0

    def get_head_commit(self) -> str:
        """Returns the HEAD commit SHA of the isolated workspace."""
        res = self.run_git(["rev-parse", "HEAD"], check=False)
        return res.stdout.strip()

    def dispose(self) -> None:
        """Safely cleans up the isolated workspace."""
        if not self.workspace_dir.exists():
            return

        # If created via worktree, deregister from source repo
        if self.creation_method == WorkspaceCreationMethod.WORKTREE:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(self.workspace_dir)],
                    cwd=str(self.source_repo),
                    capture_output=True,
                    check=False,
                    timeout=15,
                )
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                subprocess.run(
                    ["git", "worktree", "prune"],
                    cwd=str(self.source_repo),
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
            except (OSError, subprocess.SubprocessError):
                pass

        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir, onerror=_remove_readonly)


class SnapshotManager:
    """Orchestrates creation, validation, and lifecycle of clean repository snapshots."""

    def __init__(self, source_repo: Optional[Path | str] = None) -> None:
        self.source_repo = Path(source_repo).resolve() if source_repo else Path.cwd()

    def verify_baseline_clean(self) -> tuple[bool, str]:
        """Verifies that the main development repository is not dirty before evaluation."""
        try:
            res = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(self.source_repo),
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            dirty_lines = [l for l in res.stdout.splitlines() if l.strip()]
            if dirty_lines:
                return False, f"Source repository has uncommitted changes: {dirty_lines[:3]}"
            return True, "Clean"
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"Git status check failed: {e}"

    def resolve_commit(self, commit_ref: str = "HEAD") -> str:
        """Resolves a revision reference into a full 40-character SHA."""
        res = subprocess.run(
            ["git", "rev-parse", commit_ref],
            cwd=str(self.source_repo),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return res.stdout.strip()

    def create_snapshot(
        self,
        task_id: str,
        run_id: str,
        baseline_commit: Optional[str] = None,
        role: str = "agent",  # 'agent' or 'validation'
        target_dir: Optional[Path] = None,
        allow_dirty_baseline: bool = False,
    ) -> CleanRepositorySnapshot:
        """Creates an isolated clean repository snapshot."""
        # 1. Baseline Cleanliness Guarantee (Phase 3)
        if not allow_dirty_baseline:
            is_clean, reason = self.verify_baseline_clean()
            if not is_clean:
                raise ValueError(
                    f"Evaluator rejected dirty baseline repository: {reason}. "
                    f"All evaluations must start from a clean baseline."
                )

        resolved_commit = self.resolve_commit(baseline_commit or "HEAD")

        # 2. Determine isolated directory location
        if target_dir is None:
            tmp_root = Path(tempfile.gettempdir()) / "impulse_eval"
            tmp_root.mkdir(parents=True, exist_ok=True)
            workspace_dir = Path(tempfile.mkdtemp(prefix=f"eval_{role}_{task_id[:16]}_", dir=tmp_root))
        else:
            workspace_dir = target_dir
            workspace_dir.mkdir(parents=True, exist_ok=True)

        creation_method = WorkspaceCreationMethod.WORKTREE

        # 3. Attempt Git Worktree first
        worktree_created = False
        try:
            wt_res = subprocess.run(
                ["git", "worktree", "add", "--detach", str(workspace_dir), resolved_commit],
                cwd=str(self.source_repo),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if wt_res.returncode == 0:
                worktree_created = True
        except (OSError, subprocess.SubprocessError):
            worktree_created = False

        # 4. Fallback to Shared Clone if worktree not viable
        if not worktree_created:
            creation_method = WorkspaceCreationMethod.CLONE
            # Clean clone
            subprocess.run(
                ["git", "clone", "--shared", "--no-checkout", str(self.source_repo), str(workspace_dir)],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            subprocess.run(
                ["git", "checkout", resolved_commit],
                cwd=str(workspace_dir),
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

        # 5. Configure standard git exclude per HARNESS_README.md Section 4.1
        git_dir = workspace_dir / ".git"
        exclude_path: Optional[Path] = None
        if git_dir.is_file():
            # In worktrees, .git is a file pointing to gitdir: ...
            with open(git_dir, "r", encoding="utf-8") as f:
                line = f.read().strip()
            if line.startswith("gitdir:"):
                actual_git_dir = Path(line.split("gitdir:", 1)[1].strip())
                info_dir = actual_git_dir / "info"
                info_dir.mkdir(parents=True, exist_ok=True)
                exclude_path = info_dir / "exclude"
                with open(exclude_path, "a", encoding="utf-8") as f:
                    f.write(STANDARD_GIT_EXCLUDE)
        elif git_dir.is_dir():
            info_dir = git_dir / "info"
            info_dir.mkdir(parents=True, exist_ok=True)
            exclude_path = info_dir / "exclude"
            with open(exclude_path, "a", encoding="utf-8") as f:
                f.write(STANDARD_GIT_EXCLUDE)

        snapshot = CleanRepositorySnapshot(
            workspace_dir=workspace_dir,
            baseline_commit=resolved_commit,
            task_id=task_id,
            run_id=run_id,
            role=role,
            creation_method=creation_method,
            source_repo=self.source_repo,
            exclude_file=exclude_path,
        )

        # 6. Verify initial cleanliness of snapshot
        if not snapshot.is_clean():
            snapshot.dispose()
            raise RuntimeError(
                f"Failed to create clean snapshot: initial working tree in {workspace_dir} is dirty"
            )

        return snapshot
