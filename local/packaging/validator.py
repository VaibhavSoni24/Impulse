"""Orchestrator for submission package validation across directories and ZIP archives."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

from local.packaging.adapter_validator import validate_adapters
from local.packaging.archive_security import compute_file_sha256, inspect_archive_security
from local.packaging.config_validator import ConfigurationValidator
from local.packaging.constants import (
    ALLOWED_FILE_EXTENSIONS,
    MAX_FILE_COUNT,
    MAX_TOTAL_SIZE_BYTES,
    MAX_YAML_FILES,
    MAX_YAML_SIZE_BYTES,
)
from local.packaging.models import (
    CheckCategory,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    PackageValidationResult,
    ValidatorConfig,
)
from local.packaging.reader import (
    ArchivePackageReader,
    DirectoryPackageReader,
    PackageReader,
    normalize_rel_path,
)
from local.packaging.secret_scanner import scan_package_secrets_and_hygiene
from local.packaging.skill_validator import validate_skills


def compute_directory_hash(dir_path: Path) -> str:
    """Computes deterministic hash across sorted files in a directory for mutation verification."""
    h = hashlib.sha256()
    for f in sorted(dir_path.rglob("*")):
        if f.is_file():
            rel = f.relative_to(dir_path).as_posix()
            try:
                size = f.stat().st_size
                mtime = f.stat().st_mtime_ns
                h.update(f"{rel}:{size}:{mtime}\n".encode("utf-8"))
            except Exception:
                pass
    return h.hexdigest()


class PackageValidator:
    """Validates IMPULSE agent submission packages (candidate directories or ZIP archives)."""

    def __init__(
        self,
        target_path: Path | str,
        config: Optional[ValidatorConfig] = None,
    ) -> None:
        self.target_path = Path(target_path).resolve()
        self.config = config or ValidatorConfig()

    def validate(self) -> PackageValidationResult:
        """Executes all validation phases and returns a comprehensive result."""
        target = self.target_path
        checks: list[CheckResult] = []
        is_zip = target.is_file() and (target.suffix.lower() == ".zip" or not target.is_dir())

        target_type = "ARCHIVE_ZIP" if is_zip else "DIRECTORY"
        result = PackageValidationResult(
            target_path=str(target),
            target_type=target_type,
            overall_valid=False,
            checks=checks,
        )

        # Mutation safety baseline hash
        initial_hash = compute_file_sha256(target) if is_zip else compute_directory_hash(target)

        reader: Optional[PackageReader] = None
        archive_metadata = None

        try:
            if is_zip:
                # 1. Archive Security & Structural Integrity Phase
                arch_checks, metadata = inspect_archive_security(target, self.config)
                checks.extend(arch_checks)
                archive_metadata = metadata
                result.archive_metadata = metadata

                # If archive is missing or unreadable as a ZIP, stop early
                if any(
                    c.check_id in ("ARCH_EXISTS", "ARCH_VALID_ZIP", "ARCH_OPEN")
                    and c.status == CheckStatus.FAIL
                    for c in arch_checks
                ):
                    result.compute_counts(self.config.strict_mode)
                    return result

                reader = ArchivePackageReader(target)
                root_config = metadata.root_config_path if metadata else "agent.yaml"
            else:
                # 1. Directory Structure Inspection
                if not target.exists() or not target.is_dir():
                    checks.append(
                        CheckResult(
                            check_id="DIR_EXISTS",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=str(target),
                            expected="Directory exists",
                            observed="Directory not found",
                            diagnostic=f"Submission directory does not exist: {target}",
                            rule_ref="PLAN.md Stage 47",
                        )
                    )
                    result.compute_counts(self.config.strict_mode)
                    return result

                reader = DirectoryPackageReader(target)
                self._inspect_directory_structure(target, checks)

                root_configs = [
                    f for f in ["agent.yaml", "agent.yml", "root_agent.yaml", "root_agent.yml"]
                    if reader.exists(f)
                ]
                if not root_configs:
                    checks.append(
                        CheckResult(
                            check_id="DIR_ROOT_CONFIG",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=str(target),
                            expected="Exactly one root agent.yaml or agent.yml",
                            observed="Zero root configs found",
                            diagnostic="MissingRootConfigError: No agent.yaml / agent.yml found in submission root.",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )
                    root_config = "agent.yaml"
                elif len(root_configs) > 1:
                    checks.append(
                        CheckResult(
                            check_id="DIR_ROOT_CONFIG",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=str(target),
                            expected="Exactly one root agent.yaml or agent.yml",
                            observed=f"Multiple root configs: {root_configs}",
                            diagnostic=f"MultipleRootConfigsError: Multiple root configs found: {root_configs}.",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )
                    root_config = root_configs[0]
                else:
                    root_config = root_configs[0]
                    checks.append(
                        CheckResult(
                            check_id="DIR_ROOT_CONFIG",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.INFO,
                            target=root_config,
                            expected="Exactly one root config in submission directory",
                            observed=f"Found canonical '{root_config}'",
                            diagnostic=f"Canonical root config '{root_config}' found.",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )

            # Record file counts & sizes from reader
            all_entries = reader.list_entries()
            result.total_files = len(all_entries)
            result.total_size_bytes = sum(reader.file_size(e) for e in all_entries)
            result.yaml_files = sum(1 for e in all_entries if e.endswith((".yaml", ".yml")))

            # 2. Configuration & Include Validation Phase
            cfg_validator = ConfigurationValidator(reader, self.config)
            cfg_checks = cfg_validator.validate_package_configuration(root_config)
            checks.extend(cfg_checks)

            result.discovered_models = sorted(cfg_validator.discovered_models)
            declared_base_model = result.discovered_models[0] if result.discovered_models else None

            # 3. Skill Manifest Validation Phase
            skill_checks = validate_skills(reader, cfg_validator.discovered_skills, self.config)
            checks.extend(skill_checks)

            # 4. Optional PEFT LoRA Adapter Validation Phase
            adapter_checks = validate_adapters(
                reader, cfg_validator.discovered_adapters, declared_base_model, self.config
            )
            checks.extend(adapter_checks)

            # 5. Secret Scanning & Development Artifact Hygiene Phase
            hygiene_checks = scan_package_secrets_and_hygiene(reader, self.config)
            checks.extend(hygiene_checks)

        finally:
            if reader:
                try:
                    reader.close()
                except Exception:
                    pass

        # 6. Read-Only Mutation Safety Verification
        final_hash = compute_file_sha256(target) if is_zip else compute_directory_hash(target)
        if initial_hash == final_hash:
            checks.append(
                CheckResult(
                    check_id="MUTATION_SAFETY_INVARIANT",
                    category=CheckCategory.MUTATION_SAFETY,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target=str(target),
                    expected="Target package remains 100% byte-for-byte immutable during validation",
                    observed="Hash before == Hash after (read-only verified)",
                    diagnostic="Read-only validation verified. Package target was not mutated.",
                    rule_ref="PLAN.md Stage 47",
                )
            )
        else:
            checks.append(
                CheckResult(
                    check_id="MUTATION_SAFETY_INVARIANT",
                    category=CheckCategory.MUTATION_SAFETY,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=str(target),
                    expected="Target package remains immutable",
                    observed="Target package modified during validation",
                    diagnostic="MutationViolation: Package files changed during validation.",
                    rule_ref="PLAN.md Stage 47",
                )
            )

        result.compute_counts(self.config.strict_mode)
        return result

    def _inspect_directory_structure(self, root_dir: Path, checks: list[CheckResult]) -> None:
        """Inspects directory file count, total size, symlinks, and extensions."""
        total_files = 0
        total_size = 0
        yaml_count = 0

        for entry in root_dir.rglob("*"):
            if entry.is_symlink():
                resolved = entry.resolve()
                if not str(resolved).startswith(str(root_dir)):
                    checks.append(
                        CheckResult(
                            check_id="DIR_SYMLINK_ESCAPE",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=str(entry),
                            expected="Symlinks resolve inside submission root",
                            observed=f"Symlink resolves outside root: {resolved}",
                            diagnostic=f"PathTraversalError: Symlink {entry.name} resolves outside root: {resolved}.",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )

            if entry.is_file():
                total_files += 1
                try:
                    size = entry.stat().st_size
                except Exception:
                    size = 0
                total_size += size
                ext = entry.suffix.lower()

                if ext in (".yaml", ".yml"):
                    yaml_count += 1
                    if size > MAX_YAML_SIZE_BYTES:
                        checks.append(
                            CheckResult(
                                check_id="DIR_YAML_SIZE",
                                category=CheckCategory.SCHEMA_CONFIG,
                                status=CheckStatus.FAIL,
                                severity=CheckSeverity.FATAL,
                                target=entry.name,
                                expected=f"YAML file size <= {MAX_YAML_SIZE_BYTES} bytes",
                                observed=f"{size:,} bytes",
                                diagnostic=f"YAML file {entry.name} exceeds {MAX_YAML_SIZE_BYTES} bytes limit.",
                                rule_ref="HARNESS_README.md Section 2.4",
                            )
                        )

                if ext not in ALLOWED_FILE_EXTENSIONS:
                    checks.append(
                        CheckResult(
                            check_id="DIR_ALLOWED_EXTENSIONS",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=str(entry.relative_to(root_dir)),
                            expected=f"Extension in {sorted(ALLOWED_FILE_EXTENSIONS)}",
                            observed=f"Disallowed extension '{ext}'",
                            diagnostic=f"ProhibitedFileError: Disallowed extension '{ext}' on {entry.relative_to(root_dir)}.",
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )

        if total_files > MAX_FILE_COUNT:
            checks.append(
                CheckResult(
                    check_id="DIR_FILE_COUNT",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=str(root_dir),
                    expected=f"File count <= {MAX_FILE_COUNT}",
                    observed=f"{total_files} files",
                    diagnostic=f"File count {total_files} exceeds limit of {MAX_FILE_COUNT}.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )

        if total_size > MAX_TOTAL_SIZE_BYTES:
            checks.append(
                CheckResult(
                    check_id="DIR_TOTAL_SIZE",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=str(root_dir),
                    expected=f"Total size <= {MAX_TOTAL_SIZE_BYTES} bytes (< 3 GiB)",
                    observed=f"{total_size:,} bytes",
                    diagnostic=f"Total size {total_size:,} exceeds limit of {MAX_TOTAL_SIZE_BYTES} bytes (< 3 GiB).",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )
