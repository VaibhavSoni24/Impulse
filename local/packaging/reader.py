"""Unified package reader abstraction for directories and ZIP archives.

Provides safe in-memory or bounded filesystem access to package contents
without extracting untrusted archives into the workspace.
"""

from __future__ import annotations

import abc
from pathlib import Path, PurePosixPath
from typing import Optional
import zipfile


class PackageReader(abc.ABC):
    """Abstract interface for inspecting package contents."""

    @property
    @abc.abstractmethod
    def target_type(self) -> str:
        """Target type: 'DIRECTORY' or 'ARCHIVE_ZIP'."""
        pass

    @property
    @abc.abstractmethod
    def root_display_path(self) -> str:
        """Human-readable path to the target."""
        pass

    @abc.abstractmethod
    def list_entries(self) -> list[str]:
        """Returns sorted list of all file member paths normalized as POSIX relative paths."""
        pass

    @abc.abstractmethod
    def exists(self, rel_path: str) -> bool:
        """Returns True if the member exists as a file."""
        pass

    @abc.abstractmethod
    def is_dir(self, rel_path: str) -> bool:
        """Returns True if the path represents a directory inside the package."""
        pass

    @abc.abstractmethod
    def read_text(self, rel_path: str, encoding: str = "utf-8") -> str:
        """Reads text content of a package file."""
        pass

    @abc.abstractmethod
    def read_bytes(self, rel_path: str) -> bytes:
        """Reads raw bytes of a package file."""
        pass

    @abc.abstractmethod
    def file_size(self, rel_path: str) -> int:
        """Returns uncompressed size in bytes for a file."""
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """Releases underlying resources."""
        pass

    def __enter__(self) -> PackageReader:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def normalize_rel_path(path_str: str) -> str:
    """Normalizes relative posix path string (strips leading ./ or /, converts backslashes)."""
    cleaned = path_str.replace("\\", "/").strip()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("/")
    return cleaned


class DirectoryPackageReader(PackageReader):
    """Reads package contents directly from a local directory."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root_path = Path(root_dir).resolve()
        if not self.root_path.exists() or not self.root_path.is_dir():
            raise FileNotFoundError(f"Package directory not found: {self.root_path}")

    @property
    def target_type(self) -> str:
        return "DIRECTORY"

    @property
    def root_display_path(self) -> str:
        return str(self.root_path)

    def _resolve_safe(self, rel_path: str) -> Optional[Path]:
        norm = normalize_rel_path(rel_path)
        try:
            target = (self.root_path / norm).resolve()
            if not str(target).startswith(str(self.root_path)):
                return None
            return target
        except Exception:
            return None

    def list_entries(self) -> list[str]:
        entries: list[str] = []
        for item in self.root_path.rglob("*"):
            if item.is_file():
                rel = item.relative_to(self.root_path).as_posix()
                entries.append(rel)
        return sorted(entries)

    def exists(self, rel_path: str) -> bool:
        p = self._resolve_safe(rel_path)
        return p is not None and p.exists() and p.is_file()

    def is_dir(self, rel_path: str) -> bool:
        p = self._resolve_safe(rel_path)
        return p is not None and p.exists() and p.is_dir()

    def read_text(self, rel_path: str, encoding: str = "utf-8") -> str:
        p = self._resolve_safe(rel_path)
        if p is None or not p.exists() or not p.is_file():
            raise FileNotFoundError(f"File not found in package directory: {rel_path}")
        return p.read_text(encoding=encoding)

    def read_bytes(self, rel_path: str) -> bytes:
        p = self._resolve_safe(rel_path)
        if p is None or not p.exists() or not p.is_file():
            raise FileNotFoundError(f"File not found in package directory: {rel_path}")
        return p.read_bytes()

    def file_size(self, rel_path: str) -> int:
        p = self._resolve_safe(rel_path)
        if p is None or not p.exists() or not p.is_file():
            raise FileNotFoundError(f"File not found in package directory: {rel_path}")
        return p.stat().st_size

    def close(self) -> None:
        pass


class ArchivePackageReader(PackageReader):
    """Reads package contents virtually from a ZIP archive without filesystem extraction."""

    def __init__(self, archive_path: Path | str) -> None:
        self.archive_path = Path(archive_path).resolve()
        if not self.archive_path.exists() or not self.archive_path.is_file():
            raise FileNotFoundError(f"Archive file not found: {self.archive_path}")

        self.zf = zipfile.ZipFile(self.archive_path, mode="r")
        self._members: dict[str, zipfile.ZipInfo] = {}
        self._dirs: set[str] = set()

        for info in self.zf.infolist():
            raw_name = info.filename
            norm = normalize_rel_path(raw_name)
            if raw_name.endswith("/"):
                # Explicit directory entry in zip
                self._dirs.add(norm.rstrip("/"))
            else:
                self._members[norm] = info
                # Add implicit parent directories
                parts = norm.split("/")
                for i in range(1, len(parts)):
                    self._dirs.add("/".join(parts[:i]))

    @property
    def target_type(self) -> str:
        return "ARCHIVE_ZIP"

    @property
    def root_display_path(self) -> str:
        return str(self.archive_path)

    def list_entries(self) -> list[str]:
        return sorted(self._members.keys())

    def exists(self, rel_path: str) -> bool:
        norm = normalize_rel_path(rel_path)
        return norm in self._members

    def is_dir(self, rel_path: str) -> bool:
        norm = normalize_rel_path(rel_path).rstrip("/")
        return norm in self._dirs

    def read_text(self, rel_path: str, encoding: str = "utf-8") -> str:
        norm = normalize_rel_path(rel_path)
        if norm not in self._members:
            raise FileNotFoundError(f"File not found in archive: {rel_path}")
        raw_bytes = self.zf.read(self._members[norm].filename)
        return raw_bytes.decode(encoding=encoding)

    def read_bytes(self, rel_path: str) -> bytes:
        norm = normalize_rel_path(rel_path)
        if norm not in self._members:
            raise FileNotFoundError(f"File not found in archive: {rel_path}")
        return self.zf.read(self._members[norm].filename)

    def file_size(self, rel_path: str) -> int:
        norm = normalize_rel_path(rel_path)
        if norm not in self._members:
            raise FileNotFoundError(f"File not found in archive: {rel_path}")
        return self._members[norm].file_size

    def close(self) -> None:
        try:
            self.zf.close()
        except Exception:
            pass
