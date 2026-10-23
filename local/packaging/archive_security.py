"""ZIP archive security, central directory inspection, and path containment checks."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
from typing import Optional
import zipfile

from local.packaging.constants import (
    ALLOWED_FILE_EXTENSIONS,
    COMPRESSION_RATIO_MIN_UNCOMPRESSED_SIZE,
    MAX_FILE_COUNT,
    MAX_TOTAL_SIZE_BYTES,
    MAX_YAML_FILES,
    MAX_YAML_SIZE_BYTES,
    PROHIBITED_WEIGHT_EXTENSIONS,
    RULESET_VERSION,
    SUSPICIOUS_COMPRESSION_RATIO_THRESHOLD,
    VALIDATOR_VERSION,
)
from local.packaging.models import (
    ArchiveMetadata,
    CheckCategory,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    ValidatorConfig,
)
from local.packaging.reader import normalize_rel_path


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def inspect_archive_security(
    archive_path: Path,
    config: Optional[ValidatorConfig] = None,
) -> tuple[list[CheckResult], Optional[ArchiveMetadata]]:
    """Performs deep security and structural validation directly on a ZIP archive."""
    checks: list[CheckResult] = []
    cfg = config or ValidatorConfig()

    target_str = str(archive_path)

    # 1. Existence and basic readability
    if not archive_path.exists() or not archive_path.is_file():
        checks.append(
            CheckResult(
                check_id="ARCH_EXISTS",
                category=CheckCategory.ARCHIVE_SECURITY,
                status=CheckStatus.FAIL,
                severity=CheckSeverity.FATAL,
                target=target_str,
                expected="Archive file exists and is a regular file",
                observed="File does not exist or is not a file",
                diagnostic=f"Submission archive not found: {archive_path}",
                rule_ref="PLAN.md Stage 47",
            )
        )
        return checks, None

    checks.append(
        CheckResult(
            check_id="ARCH_EXISTS",
            category=CheckCategory.ARCHIVE_SECURITY,
            status=CheckStatus.PASS,
            severity=CheckSeverity.INFO,
            target=target_str,
            expected="Archive file exists",
            observed="Archive file exists and is readable",
            diagnostic=f"Archive verified at {archive_path.name}",
            rule_ref="PLAN.md Stage 47",
        )
    )

    # 2. Valid ZIP format
    if not zipfile.is_zipfile(archive_path):
        checks.append(
            CheckResult(
                check_id="ARCH_VALID_ZIP",
                category=CheckCategory.ARCHIVE_SECURITY,
                status=CheckStatus.FAIL,
                severity=CheckSeverity.FATAL,
                target=target_str,
                expected="File is a valid PKZIP archive",
                observed="File fails zipfile.is_zipfile check",
                diagnostic=f"Archive {archive_path.name} is not a valid ZIP file or has invalid headers.",
                rule_ref="HARNESS_README.md Section 2.2",
            )
        )
        return checks, None

    checks.append(
        CheckResult(
            check_id="ARCH_VALID_ZIP",
            category=CheckCategory.ARCHIVE_SECURITY,
            status=CheckStatus.PASS,
            severity=CheckSeverity.INFO,
            target=target_str,
            expected="File is a valid PKZIP archive",
            observed="Valid PKZIP header confirmed",
            diagnostic="PKZIP signature and structure verified.",
            rule_ref="HARNESS_README.md Section 2.2",
        )
    )

    try:
        zf = zipfile.ZipFile(archive_path, mode="r")
    except Exception as e:
        checks.append(
            CheckResult(
                check_id="ARCH_OPEN",
                category=CheckCategory.ARCHIVE_SECURITY,
                status=CheckStatus.FAIL,
                severity=CheckSeverity.FATAL,
                target=target_str,
                expected="Archive opens successfully",
                observed=f"ZipFile open error: {e}",
                diagnostic=f"Could not open archive {archive_path.name}: {e}",
                rule_ref="HARNESS_README.md Section 2.2",
            )
        )
        return checks, None

    try:
        # 3. ZIP integrity test (CRC32 verify)
        try:
            corrupted = zf.testzip()
        except Exception as e:
            corrupted = f"corrupt_archive_data ({type(e).__name__}: {e})"

        if corrupted is not None:
            checks.append(
                CheckResult(
                    check_id="ARCH_INTEGRITY",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=str(corrupted),
                    expected="All ZIP member CRC-32 checksums match",
                    observed=f"CRC mismatch or corrupt member data in {corrupted}",
                    diagnostic=f"Corrupt member '{corrupted}' detected by ZIP central directory CRC check.",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
        else:
            checks.append(
                CheckResult(
                    check_id="ARCH_INTEGRITY",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target=target_str,
                    expected="All member CRC-32 checksums match",
                    observed="Zero CRC-32 errors in archive",
                    diagnostic="All archive member checksums verified cleanly.",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )

        # 4. Member counts and size ceilings
        infolist = zf.infolist()
        total_members = len(infolist)
        total_uncompressed = sum(info.file_size for info in infolist)
        compressed_size = archive_path.stat().st_size

        if total_members > MAX_FILE_COUNT:
            checks.append(
                CheckResult(
                    check_id="ARCH_MEMBER_COUNT",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=target_str,
                    expected=f"Member count <= {MAX_FILE_COUNT}",
                    observed=f"{total_members} members",
                    diagnostic=f"Archive member count ({total_members}) exceeds ceiling of {MAX_FILE_COUNT}.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )
        else:
            checks.append(
                CheckResult(
                    check_id="ARCH_MEMBER_COUNT",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target=target_str,
                    expected=f"Member count <= {MAX_FILE_COUNT}",
                    observed=f"{total_members} members",
                    diagnostic=f"Member count ({total_members}) within bounds.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )

        max_allowed_size = cfg.max_total_size_bytes or MAX_TOTAL_SIZE_BYTES
        if total_uncompressed > max_allowed_size:
            checks.append(
                CheckResult(
                    check_id="ARCH_TOTAL_SIZE",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=target_str,
                    expected=f"Total uncompressed size <= {max_allowed_size:,} bytes (< 3 GiB)",
                    observed=f"{total_uncompressed:,} bytes",
                    diagnostic=f"Uncompressed archive size ({total_uncompressed:,} bytes) exceeds limit of {max_allowed_size:,} bytes.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )
        else:
            checks.append(
                CheckResult(
                    check_id="ARCH_TOTAL_SIZE",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target=target_str,
                    expected=f"Total uncompressed size <= {max_allowed_size:,} bytes (< 3 GiB)",
                    observed=f"{total_uncompressed:,} bytes",
                    diagnostic=f"Uncompressed size ({total_uncompressed / (1024*1024):.2f} MB) complies with < 3 GiB ceiling.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )

        # 5. Member-by-member deep inspection
        seen_raw_names: set[str] = set()
        seen_normalized_lower: dict[str, str] = {}
        declared_files: set[str] = set()
        declared_dirs: set[str] = set()
        yaml_count = 0
        root_configs: list[str] = []

        for info in infolist:
            raw_name = info.filename

            # Duplicate member check
            if raw_name in seen_raw_names:
                checks.append(
                    CheckResult(
                        check_id="ARCH_NO_DUPLICATE_MEMBERS",
                        category=CheckCategory.ARCHIVE_SECURITY,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=raw_name,
                        expected="Archive member names are unique",
                        observed="Duplicate member entry in central directory",
                        diagnostic=f"Duplicate archive member detected: '{raw_name}'.",
                        rule_ref="PLAN.md Stage 47",
                    )
                )
            seen_raw_names.add(raw_name)

            # Null byte check
            if "\0" in raw_name:
                checks.append(
                    CheckResult(
                        check_id="ARCH_NO_NULL_BYTES",
                        category=CheckCategory.ARCHIVE_SECURITY,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=repr(raw_name),
                        expected="No null bytes in member path",
                        observed="Null byte present in path name",
                        diagnostic=f"Null byte detected in member name: {repr(raw_name)}.",
                        rule_ref="HARNESS_README.md Section 2.2",
                    )
                )

            # Symlink check via external_attr
            # Unix file type is stored in the upper 16 bits of external_attr.
            # S_IFLNK is 0o120000.
            mode = (info.external_attr >> 16) & 0xFFFF
            if (mode & 0o170000) == 0o120000:
                checks.append(
                    CheckResult(
                        check_id="ARCH_NO_SYMLINKS",
                        category=CheckCategory.ARCHIVE_SECURITY,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=raw_name,
                        expected="Archive contains only regular files or directories, zero symlinks",
                        observed="Member has Unix S_IFLNK (symlink) external attribute",
                        diagnostic=f"Prohibited symlink member detected: '{raw_name}'.",
                        rule_ref="HARNESS_README.md Section 2.2 & 2.4",
                    )
                )

            # Encryption check
            if info.flag_bits & 0x1:
                checks.append(
                    CheckResult(
                        check_id="ARCH_NO_ENCRYPTION",
                        category=CheckCategory.ARCHIVE_SECURITY,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=raw_name,
                        expected="Archive members are unencrypted",
                        observed="Member flag_bits bit 0 is set (encrypted)",
                        diagnostic=f"Encrypted member detected: '{raw_name}'. Encrypted archives are unsupported.",
                        rule_ref="PLAN.md Stage 47",
                    )
                )

            # Path attack checks: Absolute, Drive, UNC, Traversal
            cleaned = raw_name.replace("\\", "/")
            if cleaned.startswith("/") or raw_name.startswith("\\"):
                checks.append(
                    CheckResult(
                        check_id="ARCH_NO_ABSOLUTE_PATH",
                        category=CheckCategory.ARCHIVE_SECURITY,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=raw_name,
                        expected="Archive paths are strictly relative",
                        observed="Path starts with root slash",
                        diagnostic=f"Absolute path member detected: '{raw_name}'.",
                        rule_ref="HARNESS_README.md Section 2.2",
                    )
                )

            if re.match(r"^[a-zA-Z]:", raw_name):
                checks.append(
                    CheckResult(
                        check_id="ARCH_NO_DRIVE_PATH",
                        category=CheckCategory.ARCHIVE_SECURITY,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=raw_name,
                        expected="Archive paths are strictly relative",
                        observed="Path starts with drive letter",
                        diagnostic=f"Windows drive-prefixed path detected: '{raw_name}'.",
                        rule_ref="PLAN.md Stage 47",
                    )
                )

            if cleaned.startswith("//") or raw_name.startswith("\\\\"):
                checks.append(
                    CheckResult(
                        check_id="ARCH_NO_UNC_PATH",
                        category=CheckCategory.ARCHIVE_SECURITY,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=raw_name,
                        expected="Archive paths are strictly relative",
                        observed="Path starts with UNC prefix",
                        diagnostic=f"UNC network path detected: '{raw_name}'.",
                        rule_ref="PLAN.md Stage 47",
                    )
                )

            # Check for '..' traversal components
            raw_parts = [p for p in re.split(r"[/\\]", raw_name) if p]
            if ".." in raw_parts:
                checks.append(
                    CheckResult(
                        check_id="ARCH_NO_TRAVERSAL",
                        category=CheckCategory.ARCHIVE_SECURITY,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=raw_name,
                        expected="No '..' directory traversal components",
                        observed=f"'..' component found in path parts {raw_parts}",
                        diagnostic=f"Directory traversal component '..' detected in member: '{raw_name}'.",
                        rule_ref="HARNESS_README.md Section 2.2",
                    )
                )

            # Compression bomb check
            if info.file_size >= COMPRESSION_RATIO_MIN_UNCOMPRESSED_SIZE:
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > SUSPICIOUS_COMPRESSION_RATIO_THRESHOLD:
                    checks.append(
                        CheckResult(
                            check_id="ARCH_SUSPICIOUS_COMPRESSION",
                            category=CheckCategory.ARCHIVE_SECURITY,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=raw_name,
                            expected=f"Compression ratio <= {SUSPICIOUS_COMPRESSION_RATIO_THRESHOLD}:1",
                            observed=f"Compression ratio {ratio:.1f}:1 ({info.file_size:,} uncompressed / {info.compress_size:,} compressed)",
                            diagnostic=f"Potential zip bomb detected in '{raw_name}': expansion ratio {ratio:.1f}:1 exceeds safety ceiling.",
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )

            # Normalized path collisions and case collisions
            norm = normalize_rel_path(raw_name)
            is_dir_entry = raw_name.endswith("/")
            norm_clean = norm.rstrip("/")

            if norm_clean:
                norm_lower = norm_clean.lower()
                if norm_lower in seen_normalized_lower and seen_normalized_lower[norm_lower] != norm_clean:
                    checks.append(
                        CheckResult(
                            check_id="ARCH_NO_CASE_COLLISION",
                            category=CheckCategory.ARCHIVE_SECURITY,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=raw_name,
                            expected="Unique case-insensitive member paths",
                            observed=f"'{norm_clean}' collides with '{seen_normalized_lower[norm_lower]}'",
                            diagnostic=f"Case-insensitive path collision detected: '{norm_clean}' collides with '{seen_normalized_lower[norm_lower]}'.",
                            rule_ref="PLAN.md Stage 47",
                        )
                    )
                seen_normalized_lower[norm_lower] = norm_clean

            # File/Directory collisions
            if is_dir_entry:
                declared_dirs.add(norm_clean)
                if norm_clean in declared_files:
                    checks.append(
                        CheckResult(
                            check_id="ARCH_NO_FILE_DIR_COLLISION",
                            category=CheckCategory.ARCHIVE_SECURITY,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm_clean,
                            expected="Paths do not collide as both file and directory",
                            observed=f"'{norm_clean}' is declared as both a file and directory entry",
                            diagnostic=f"File/Directory collision: '{norm_clean}' exists as both file and directory.",
                            rule_ref="PLAN.md Stage 47",
                        )
                    )
            else:
                declared_files.add(norm_clean)
                if norm_clean in declared_dirs:
                    checks.append(
                        CheckResult(
                            check_id="ARCH_NO_FILE_DIR_COLLISION",
                            category=CheckCategory.ARCHIVE_SECURITY,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm_clean,
                            expected="Paths do not collide as both file and directory",
                            observed=f"'{norm_clean}' is declared as both a file and directory entry",
                            diagnostic=f"File/Directory collision: '{norm_clean}' exists as both file and directory.",
                            rule_ref="PLAN.md Stage 47",
                        )
                    )
                # Check if an existing file path is a prefix directory of this file
                parts = norm_clean.split("/")
                for i in range(1, len(parts)):
                    parent_part = "/".join(parts[:i])
                    if parent_part in declared_files:
                        checks.append(
                            CheckResult(
                                check_id="ARCH_NO_FILE_DIR_COLLISION",
                                category=CheckCategory.ARCHIVE_SECURITY,
                                status=CheckStatus.FAIL,
                                severity=CheckSeverity.FATAL,
                                target=norm_clean,
                                expected="Path prefixes do not collide with regular files",
                                observed=f"Parent '{parent_part}' is declared as a regular file",
                                diagnostic=f"Path collision: member '{norm_clean}' requires '{parent_part}' to be a directory, but it is declared as a file.",
                                rule_ref="PLAN.md Stage 47",
                            )
                        )

            # Extension and individual file checks for non-directory members
            if not is_dir_entry:
                ext = Path(norm_clean).suffix.lower()

                # Check prohibited weight formats
                if ext in PROHIBITED_WEIGHT_EXTENSIONS:
                    checks.append(
                        CheckResult(
                            check_id="ARCH_NO_PROHIBITED_WEIGHTS",
                            category=CheckCategory.ARCHIVE_SECURITY,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm_clean,
                            expected="No pickle or disallowed binary weights (.safetensors only)",
                            observed=f"Disallowed weight extension '{ext}'",
                            diagnostic=f"Prohibited weight format '{ext}' in '{norm_clean}'. Only .safetensors is allowed for weights.",
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )

                # Check allowed file extensions
                if ext not in ALLOWED_FILE_EXTENSIONS:
                    checks.append(
                        CheckResult(
                            check_id="ARCH_ALLOWED_EXTENSIONS",
                            category=CheckCategory.ARCHIVE_SECURITY,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm_clean,
                            expected=f"Extension in {sorted(ALLOWED_FILE_EXTENSIONS)}",
                            observed=f"Disallowed extension '{ext}'",
                            diagnostic=f"Disallowed file extension '{ext}' on member '{norm_clean}'.",
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )

                if ext in (".yaml", ".yml"):
                    yaml_count += 1
                    if info.file_size > MAX_YAML_SIZE_BYTES:
                        checks.append(
                            CheckResult(
                                check_id="ARCH_MAX_YAML_SIZE",
                                category=CheckCategory.ARCHIVE_SECURITY,
                                status=CheckStatus.FAIL,
                                severity=CheckSeverity.FATAL,
                                target=norm_clean,
                                expected=f"YAML file size <= {MAX_YAML_SIZE_BYTES} bytes",
                                observed=f"{info.file_size:,} bytes",
                                diagnostic=f"YAML member '{norm_clean}' exceeds size limit ({info.file_size:,} > {MAX_YAML_SIZE_BYTES}).",
                                rule_ref="HARNESS_README.md Section 2.4",
                            )
                        )

                # Check if this member is a root config
                if norm_clean in ("agent.yaml", "agent.yml", "root_agent.yaml", "root_agent.yml"):
                    root_configs.append(norm_clean)

        # YAML file count check
        if yaml_count > MAX_YAML_FILES:
            checks.append(
                CheckResult(
                    check_id="ARCH_YAML_COUNT",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=target_str,
                    expected=f"YAML file count <= {MAX_YAML_FILES}",
                    observed=f"{yaml_count} YAML files",
                    diagnostic=f"Total YAML files ({yaml_count}) exceeds limit of {MAX_YAML_FILES}.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )

        # 6. Canonical root config discovery at archive root
        if not root_configs:
            # Check if an agent.yaml was placed in a subdirectory (e.g. submission/agent.yaml)
            nested_agent_yamls = [
                m for m in declared_files
                if Path(m).name in ("agent.yaml", "agent.yml", "root_agent.yaml", "root_agent.yml")
            ]
            if nested_agent_yamls:
                diag = f"Missing root config: agent.yaml is nested under subdirectory '{nested_agent_yamls[0]}' rather than directly at archive root."
            else:
                diag = "MissingRootConfigError: No agent.yaml / agent.yml found at submission archive root."

            checks.append(
                CheckResult(
                    check_id="ARCH_ROOT_CONFIG",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=target_str,
                    expected="Exactly one canonical root agent.yaml or agent.yml at archive root",
                    observed="Zero root configs at archive root",
                    diagnostic=diag,
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            canonical_root = ""
        elif len(root_configs) > 1:
            checks.append(
                CheckResult(
                    check_id="ARCH_ROOT_CONFIG",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=target_str,
                    expected="Exactly one canonical root agent.yaml at archive root",
                    observed=f"Multiple root configs: {root_configs}",
                    diagnostic=f"MultipleRootConfigsError: Multiple root configs found at archive root: {root_configs}.",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            canonical_root = root_configs[0]
        else:
            canonical_root = root_configs[0]
            checks.append(
                CheckResult(
                    check_id="ARCH_ROOT_CONFIG",
                    category=CheckCategory.ARCHIVE_SECURITY,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target=canonical_root,
                    expected="Exactly one root config at archive root",
                    observed=f"Found canonical '{canonical_root}' at archive root",
                    diagnostic=f"Canonical entrypoint '{canonical_root}' discovered at archive root.",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )

        # Compute archive metadata
        sha256_hash = compute_file_sha256(archive_path)
        metadata = ArchiveMetadata(
            archive_sha256=sha256_hash,
            compressed_size=compressed_size,
            uncompressed_size=total_uncompressed,
            member_count=total_members,
            root_config_path=canonical_root,
            validator_version=VALIDATOR_VERSION,
            ruleset_version=RULESET_VERSION,
        )

        return checks, metadata

    finally:
        try:
            zf.close()
        except Exception:
            pass
