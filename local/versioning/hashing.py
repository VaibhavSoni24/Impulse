"""Cryptographic hashing, path normalization, and secret scanning for candidate manifests.

Provides:
- Deterministic SHA-256 file and directory hashing
- Canonical manifest hashing
- Strict zero-secrets detection
- Path normalization removing host usernames and machine paths
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from local.versioning.errors import SecretDetectedInManifestError

SECRET_PATTERNS = [
    re.compile(r"akid[a-z0-9]{16,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"hf_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"kaggle_[a-zA-Z0-9]{16,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"password\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
]

USER_PATH_PATTERN = re.compile(r"(?:[a-zA-Z]:[/\\](?:Users|home|root)[/\\][a-zA-Z0-9._-]+)", re.IGNORECASE)


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file deterministically in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_directory_manifest_hash(dir_path: Path) -> str:
    """Computes deterministic SHA-256 hash across sorted files in a directory."""
    if not dir_path.is_dir():
        return hashlib.sha256(b"").hexdigest()

    entries: List[str] = []
    for f in sorted(dir_path.rglob("*")):
        if f.is_file() and not f.name.endswith((".pyc", ".log", ".tmp")):
            rel = f.relative_to(dir_path).as_posix()
            sha = compute_file_sha256(f)
            entries.append(f"{rel}:{sha}")

    canonical_repr = "\n".join(entries).encode("utf-8")
    return hashlib.sha256(canonical_repr).hexdigest()


def compute_canonical_dict_hash(data: Dict[str, Any], exclude_keys: Optional[List[str]] = None) -> str:
    """Computes deterministic SHA-256 hash of a dictionary."""
    exclude = set(exclude_keys or ["manifest_hash"])
    filtered = {k: v for k, v in data.items() if k not in exclude}
    canonical_json = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def scan_for_secrets(val: Any) -> None:
    """Recursively scans strings, dicts, or lists for credentials."""
    if isinstance(val, str):
        for pat in SECRET_PATTERNS:
            if pat.search(val):
                raise SecretDetectedInManifestError(
                    f"Credential or secret pattern detected in candidate manifest: '{val[:25]}...'"
                )
    elif isinstance(val, dict):
        for k, v in val.items():
            scan_for_secrets(k)
            scan_for_secrets(v)
    elif isinstance(val, list):
        for item in val:
            scan_for_secrets(item)


def normalize_machine_paths(val: Any, repo_root: Optional[Path] = None) -> Any:
    """Normalizes host-specific usernames and absolute paths into relative or symbolic references."""
    root_str = repo_root.resolve().as_posix() if repo_root else ""
    if isinstance(val, str):
        # Replace repo root with relative notation
        if root_str and root_str in val.replace("\\", "/"):
            val = val.replace("\\", "/").replace(root_str, ".").lstrip("./")

        # Strip user home paths
        val = USER_PATH_PATTERN.sub("<USER_HOME>", val)
        return val
    elif isinstance(val, dict):
        return {k: normalize_machine_paths(v, repo_root) for k, v in val.items()}
    elif isinstance(val, list):
        return [normalize_machine_paths(item, repo_root) for item in val]
    return val
