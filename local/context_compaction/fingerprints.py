"""Deterministic file and content fingerprinting for Safe Context Compaction (Stage 25).

Provides SHA-256 fingerprinting for file observations, distinguishing unchanged
from changed content, preventing cross-file collapsing, and protecting secrets.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Union

from local.context_compaction.models import FileFingerprint

KEY_VAL_SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|auth|bearer)(\s*[:=]\s*['\"]?)[A-Za-z0-9_\-\.]{8,}(['\"]?)"
)
TOKEN_SECRET_PATTERN = re.compile(
    r"\b(ghp_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82})\b"
)
PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"
)


def sanitize_text(text: str) -> str:
    """Scrubs detected secret tokens and credentials from text before storing in metadata."""
    if not text:
        return ""
    sanitized = KEY_VAL_SECRET_PATTERN.sub(r"\1\2[REDACTED_SECRET]\3", text)
    sanitized = TOKEN_SECRET_PATTERN.sub("[REDACTED_SECRET]", sanitized)
    sanitized = PRIVATE_KEY_PATTERN.sub("[REDACTED_PRIVATE_KEY]", sanitized)
    return sanitized


def normalize_path(path: Union[str, Path]) -> str:
    """Normalizes path separators to POSIX forward slashes and strips leading redundant parts."""
    p_str = str(path).replace("\\", "/")
    # Remove leading current directory marker if present
    if p_str.startswith("./"):
        p_str = p_str[2:]
    return p_str


def compute_content_sha256(content: Union[str, bytes]) -> str:
    """Computes a deterministic SHA-256 hex digest of file or string content."""
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content
    return hashlib.sha256(content_bytes).hexdigest()


def compute_file_fingerprint(
    path: Union[str, Path],
    content: Union[str, bytes],
    version: int = 1,
) -> FileFingerprint:
    """Creates a deterministic FileFingerprint record for a file observation.
    
    Path is normalized to prevent platform-specific path discrepancies.
    Fingerprint depends strictly on content SHA-256 and size, never on timestamps.
    """
    norm_path = normalize_path(path)
    sha256 = compute_content_sha256(content)
    size_bytes = len(content.encode("utf-8") if isinstance(content, str) else content)

    return FileFingerprint(
        path=norm_path,
        sha256=sha256,
        size_bytes=size_bytes,
        version=version,
    )


def are_observations_identical(
    fp1: FileFingerprint,
    fp2: FileFingerprint,
) -> bool:
    """Determines if two observations represent the identical file content at the same path.
    
    Hard safety requirement:
    - Same path + same content fingerprint => duplicate observation (True)
    - Same path + different fingerprint => changed observation (False)
    - Different paths with same content => False (NEVER collapse across distinct paths)
    """
    if normalize_path(fp1.path) != normalize_path(fp2.path):
        return False
    return fp1.sha256 == fp2.sha256
