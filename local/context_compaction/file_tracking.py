"""Changed-file tracking across turns for Safe Context Compaction (Stage 25).

Maintains exact state records for inspected and modified files, tracking content
fingerprints, revision counts, relevance status, and last meaningful observations.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Union

from local.context_compaction.fingerprints import (
    compute_file_fingerprint,
    normalize_path,
    sanitize_text,
)
from local.context_compaction.models import ChangedFileRecord, FileFingerprint


class ChangedFileTracker:
    """Tracks file observations, modifications, and relevance across task turns.
    
    Guarantees that files are not silently dropped merely because their content
    is unchanged, while preventing redundant full-text re-dumps in context.
    """

    def __init__(self) -> None:
        # Keyed by normalized path
        self._records: dict[str, ChangedFileRecord] = {}
        # History of observed fingerprints per file: path -> list[FileFingerprint]
        self._fingerprints: dict[str, list[FileFingerprint]] = {}

    def record_file_observation(
        self,
        path: Union[str, Path],
        content: Union[str, bytes],
        observation_note: str = "",
        is_relevant: bool = True,
    ) -> tuple[ChangedFileRecord, bool]:
        """Records an observation of a file's content.
        
        Returns:
            (ChangedFileRecord, is_new_or_changed: bool)
        """
        norm_path = normalize_path(path)
        clean_note = sanitize_text(observation_note)[:500] if observation_note else ""

        history = self._fingerprints.setdefault(norm_path, [])
        version = len(history) + 1
        new_fp = compute_file_fingerprint(norm_path, content, version=version)

        if norm_path not in self._records:
            # First observation of this file
            history.append(new_fp)
            rec = ChangedFileRecord(
                path=norm_path,
                initial_fingerprint=new_fp.sha256,
                latest_fingerprint=new_fp.sha256,
                has_changed=False,
                edit_count=0,
                last_observation=clean_note or f"Initial read (size={new_fp.size_bytes}b)",
                is_relevant=is_relevant,
            )
            self._records[norm_path] = rec
            return rec, True

        rec = self._records[norm_path]
        rec.is_relevant = is_relevant
        if clean_note:
            rec.last_observation = clean_note

        if rec.latest_fingerprint == new_fp.sha256:
            # Content is identical: record is updated with observation time, but has_changed remains as is
            return rec, False
        else:
            # Content has changed
            history.append(new_fp)
            rec.latest_fingerprint = new_fp.sha256
            rec.has_changed = True
            rec.edit_count += 1
            if not clean_note:
                rec.last_observation = f"Modified (size={new_fp.size_bytes}b, rev={version})"
            return rec, True

    def mark_file_edit(
        self,
        path: Union[str, Path],
        new_content: Union[str, bytes],
        edit_description: str = "",
    ) -> ChangedFileRecord:
        """Explicitly logs a file modification performed during the task."""
        desc = edit_description or "File modified"
        rec, _ = self.record_file_observation(
            path=path,
            content=new_content,
            observation_note=desc,
            is_relevant=True,
        )
        return rec

    def set_relevance(self, path: Union[str, Path], is_relevant: bool) -> bool:
        """Sets the relevance flag for an actively tracked file."""
        norm_path = normalize_path(path)
        if norm_path in self._records:
            self._records[norm_path].is_relevant = is_relevant
            return True
        return False

    def get_record(self, path: Union[str, Path]) -> ChangedFileRecord | None:
        """Retrieves tracking record for a specific file path."""
        norm_path = normalize_path(path)
        return self._records.get(norm_path)

    def list_changed_files(self) -> list[ChangedFileRecord]:
        """Returns all tracked files that have changed since initial observation."""
        return [r for r in self._records.values() if r.has_changed]

    def list_tracked_files(self) -> list[ChangedFileRecord]:
        """Returns all tracked files (both unchanged and changed)."""
        return list(self._records.values())

    def get_file_versions_count(self, path: Union[str, Path]) -> int:
        """Returns the number of distinct observed versions for a file."""
        norm_path = normalize_path(path)
        return len(self._fingerprints.get(norm_path, []))

    def get_manifest_digest(self) -> str:
        """Computes a deterministic digest of all tracked files and their latest fingerprints.
        
        Used for repository-map cache validation.
        """
        sorted_keys = sorted(self._records.keys())
        manifest_str = "|".join(f"{k}:{self._records[k].latest_fingerprint}" for k in sorted_keys)
        return hashlib.sha256(manifest_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serializes tracker state to a dictionary."""
        return {
            "records": {k: v.to_dict() for k, v in self._records.items()},
            "manifest_digest": self.get_manifest_digest(),
        }
