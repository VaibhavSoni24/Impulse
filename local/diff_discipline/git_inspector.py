"""Git working tree and diff inspection subsystem (Stage 27 Phase 10 & 12).

Provides deterministic execution and parsing of:
- git status --short
- git diff --stat
- git diff --name-status
- git diff -- <file>
- git ls-files
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from local.context_compaction.fingerprints import normalize_path
from local.diff_discipline.models import GitFileStatus, GitReviewSnapshot


class GitInspector:
    """Executes and parses Git commands to inspect the repository working tree."""

    def __init__(self, repo_root: Optional[str | Path] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()

    def _run_git(self, args: list[str]) -> str:
        """Executes a git command and returns stripped stdout."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    def get_head_commit(self) -> str:
        """Returns the current HEAD commit hash."""
        return self._run_git(["rev-parse", "HEAD"])

    def get_current_branch(self) -> str:
        """Returns the current branch name."""
        branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return branch or "main"

    def get_tracked_files(self) -> list[str]:
        """Returns the list of all files currently tracked by Git."""
        out = self._run_git(["ls-files"])
        if not out:
            return []
        return [normalize_path(line) for line in out.splitlines() if line.strip()]

    def get_untracked_files(self) -> list[str]:
        """Returns untracked files not matched by .gitignore."""
        out = self._run_git(["ls-files", "--others", "--exclude-standard"])
        if not out:
            return []
        return [normalize_path(line) for line in out.splitlines() if line.strip()]

    def get_file_diff(self, rel_path: str) -> str:
        """Returns git diff output for a specific file."""
        return self._run_git(["diff", "--", rel_path])

    def parse_status_line(self, line: str) -> tuple[GitFileStatus, str]:
        """Parses a single line of `git status --short`.
        
        Example lines:
        " M path/to/file" -> (MODIFIED, "path/to/file")
        "M  path/to/file" -> (MODIFIED, "path/to/file")
        "A  path/to/file" -> (ADDED, "path/to/file")
        "D  path/to/file" -> (DELETED, "path/to/file")
        "R  old -> new"   -> (RENAMED, "new")
        "?? path/to/file" -> (UNTRACKED, "path/to/file")
        "!! path/to/file" -> (IGNORED, "path/to/file")
        """
        if len(line) < 3:
            return GitFileStatus.CLEAN, ""

        prefix = line[:2]
        path_part = line[2:].strip()

        if "->" in path_part:
            path_part = path_part.split("->")[-1].strip()

        norm_path = normalize_path(path_part)

        if prefix == "??":
            return GitFileStatus.UNTRACKED, norm_path
        elif prefix == "!!":
            return GitFileStatus.IGNORED, norm_path
        elif "A" in prefix:
            return GitFileStatus.ADDED, norm_path
        elif "D" in prefix:
            return GitFileStatus.DELETED, norm_path
        elif "R" in prefix:
            return GitFileStatus.RENAMED, norm_path
        elif "M" in prefix:
            return GitFileStatus.MODIFIED, norm_path
        else:
            return GitFileStatus.MODIFIED, norm_path

    def inspect_snapshot(self) -> GitReviewSnapshot:
        """Collects and returns a complete GitReviewSnapshot."""
        status_raw = self._run_git(["status", "--short"])
        status_lines = [s for s in status_raw.splitlines() if s.rstrip()]

        diff_stat = self._run_git(["diff", "--stat"])
        diff_name_status_raw = self._run_git(["diff", "--name-status"])

        diff_name_status: list[tuple[str, str]] = []
        for line in diff_name_status_raw.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                diff_name_status.append((parts[0], normalize_path(parts[1])))

        modified_files: list[str] = []
        untracked_files: list[str] = []
        staged_files: list[str] = []

        for line in status_lines:
            status, path = self.parse_status_line(line)
            if status == GitFileStatus.UNTRACKED:
                untracked_files.append(path)
            elif status == GitFileStatus.MODIFIED:
                modified_files.append(path)
            elif status == GitFileStatus.ADDED:
                staged_files.append(path)

        is_clean = len(status_lines) == 0 and not diff_stat

        return GitReviewSnapshot(
            status_short=status_lines,
            diff_stat=diff_stat,
            diff_name_status=diff_name_status,
            modified_files=modified_files,
            untracked_files=untracked_files,
            staged_files=staged_files,
            is_clean=is_clean,
            head_commit=self.get_head_commit(),
            branch=self.get_current_branch(),
        )
