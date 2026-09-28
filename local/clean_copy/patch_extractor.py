"""Patch extraction subsystem for Clean-Copy Evaluation (Stage 28 Phase 8, 9, 21).

Implements the official competition patch extraction sequence:
1. 'git add -N .' (stages untracked file intents while respecting .git/info/exclude)
2. 'git diff HEAD' (captures unified diff including additions from /dev/null and deletions)
3. Enforces patch security (no path traversal, no secrets, no evaluator internals)
4. Constructs a reproducible PatchBundle
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
from typing import Optional

from local.context_compaction.fingerprints import normalize_path
from local.clean_copy.models import PatchBundle
from local.clean_copy.snapshot import CleanRepositorySnapshot
from local.diff_discipline.detectors import scan_content_for_secrets


class PatchExtractionError(Exception):
    """Raised when patch extraction fails or violates security policy."""


class PatchExtractor:
    """Extracts, inspects, and verifies patch bundles from agent workspaces."""

    def __init__(self) -> None:
        pass

    def extract_patch(
        self,
        workspace: CleanRepositorySnapshot,
        run_id: str,
        task_id: str,
        candidate_id: str,
    ) -> PatchBundle:
        """Extracts the complete patch representing the agent's workspace changes."""
        root = workspace.workspace_dir

        # 1. Stage untracked intents per HARNESS_README.md Section 8.1
        try:
            workspace.run_git(["add", "-N", "."], check=True)
        except Exception as e:
            raise PatchExtractionError(f"Failed to execute 'git add -N .': {e}")

        # 2. Extract unified diff against HEAD
        try:
            proc = workspace.run_git(["diff", "HEAD"], check=True)
            diff_text = proc.stdout.replace("\r\n", "\n")
        except Exception as e:
            raise PatchExtractionError(f"Failed to execute 'git diff HEAD': {e}")

        # 3. Discover modified, added, and deleted files using git diff --name-status HEAD
        try:
            ns_proc = workspace.run_git(["diff", "--name-status", "HEAD"], check=True)
            name_status_lines = [l.strip() for l in ns_proc.stdout.splitlines() if l.strip()]
        except Exception as e:
            name_status_lines = []

        modified: list[str] = []
        new_files: list[str] = []
        deleted: list[str] = []
        changed_paths: list[str] = []

        for line in name_status_lines:
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                status_code = parts[0]
                p_norm = normalize_path(parts[1])
                if any(p_norm == ign or p_norm.startswith(ign + "/") or ("/" + ign + "/") in p_norm or p_norm.endswith(".pyc") for ign in ("__pycache__", ".pytest_cache", ".ruff_cache")):
                    continue
                changed_paths.append(p_norm)
                if status_code.startswith("A"):
                    new_files.append(p_norm)
                elif status_code.startswith("D"):
                    deleted.append(p_norm)
                elif status_code.startswith("M"):
                    modified.append(p_norm)
                else:
                    modified.append(p_norm)

        if not changed_paths:
            diff_text = ""

        # 4. Security & Scope Validation (Phase 21)
        self.validate_patch_security(diff_text, changed_paths, root)

        bundle = PatchBundle(
            run_id=run_id,
            task_id=task_id,
            candidate_id=candidate_id,
            baseline_commit=workspace.baseline_commit,
            patch_format_version="v1",
            tracked_diff=diff_text,
            new_files=new_files,
            deleted_files=deleted,
            modified_files=modified,
            changed_paths=changed_paths,
            extraction_status="OK" if diff_text.strip() else "EMPTY",
        )
        bundle.compute_sha256()
        return bundle

    def validate_patch_security(
        self,
        diff_text: str,
        changed_paths: list[str],
        workspace_root: Path,
    ) -> None:
        """Enforces security boundaries on extracted patch diff and paths."""
        # 1. Path traversal and boundary escaping
        for p in changed_paths:
            if ".." in p or p.startswith("/") or re.match(r"^[a-zA-Z]:", p):
                raise PatchExtractionError(
                    f"Security violation: Patch targets path outside workspace: '{p}'"
                )
            if p.startswith((".git/", ".git\\")):
                raise PatchExtractionError(
                    f"Security violation: Patch modifies internal Git directory: '{p}'"
                )
            if p in (".env", ".env.local", "secrets.json", "credentials.json"):
                raise PatchExtractionError(
                    f"Security violation: Patch includes sensitive environment/credential file: '{p}'"
                )

        # 2. Secret scanning in diff content
        secret_findings = scan_content_for_secrets("patch.diff", diff_text, is_tracked=False)
        if secret_findings:
            raise PatchExtractionError(
                f"Security violation: Credential detected in extracted patch diff: "
                f"{secret_findings[0].reason}"
            )
