"""Secret scanning and development artifact detection for submission packages."""

from __future__ import annotations

from pathlib import PurePosixPath
import re
from typing import Optional

from local.packaging.constants import (
    HOST_PATH_PATTERN,
    PROHIBITED_DEV_DIRECTORIES,
    PROHIBITED_DEV_FILES,
    SECRET_PATTERNS,
)
from local.packaging.models import (
    CheckCategory,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    ValidatorConfig,
)
from local.packaging.reader import PackageReader, normalize_rel_path


def redact_secret_string(val: str, prefix_len: int = 4) -> str:
    """Masks sensitive secret string for safe diagnostic reporting."""
    if len(val) <= prefix_len + 3:
        return "***REDACTED***"
    return f"{val[:prefix_len]}***REDACTED***"


def scan_package_secrets_and_hygiene(
    reader: PackageReader,
    config: Optional[ValidatorConfig] = None,
) -> list[CheckResult]:
    """Scans all package members for credentials, .env files, dev artifacts, and host paths."""
    checks: list[CheckResult] = []
    cfg = config or ValidatorConfig()

    all_entries = reader.list_entries()
    scanned_text_files = 0
    clean_secret_files = 0

    for rel_path in all_entries:
        norm = normalize_rel_path(rel_path)
        parts = [p for p in norm.split("/") if p]
        filename = parts[-1] if parts else norm
        ext = PurePosixPath(norm).suffix.lower()

        # 1. Check for .env files
        if filename == ".env" or filename.startswith(".env."):
            checks.append(
                CheckResult(
                    check_id="HYGIENE_NO_ENV_FILES",
                    category=CheckCategory.SECRET_HYGIENE,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm,
                    expected="Zero .env or environment variable files in submission",
                    observed=f"Found environment file '{norm}'",
                    diagnostic=f"Prohibited environment file '{norm}' detected in submission package.",
                    rule_ref="PLAN.md Stage 47 & .agents/rules/security.md",
                )
            )

        # 2. Check for prohibited development directories, files, logs, and tests
        if not cfg.ignore_excluded_dev_files:
            for part in parts[:-1]:
                if part in PROHIBITED_DEV_DIRECTORIES:
                    checks.append(
                        CheckResult(
                            check_id="HYGIENE_NO_DEV_DIRS",
                            category=CheckCategory.SECRET_HYGIENE,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm,
                            expected="Zero development-only directories in submission",
                            observed=f"Member inside prohibited directory '{part}'",
                            diagnostic=f"Prohibited development directory '{part}' found in package path: '{norm}'.",
                            rule_ref="PLAN.md Stage 47",
                        )
                    )
                    break

            # 3. Check for prohibited development files
            if filename in PROHIBITED_DEV_FILES:
                checks.append(
                    CheckResult(
                        check_id="HYGIENE_NO_DEV_FILES",
                        category=CheckCategory.SECRET_HYGIENE,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=norm,
                        expected="Zero development metadata files in submission",
                        observed=f"Found prohibited development file '{filename}'",
                        diagnostic=f"Prohibited development file '{norm}' detected in submission package.",
                        rule_ref="PLAN.md Stage 47",
                    )
                )

            # 4. Check for logs and temporary files
            if ext in (".log", ".tmp", ".bak", ".swp"):
                checks.append(
                    CheckResult(
                        check_id="HYGIENE_NO_TEMP_FILES",
                        category=CheckCategory.SECRET_HYGIENE,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=norm,
                        expected="Zero logs or temporary scratch files in submission",
                        observed=f"File extension '{ext}'",
                        diagnostic=f"Temporary or log file '{norm}' detected in package.",
                        rule_ref="PLAN.md Stage 47",
                    )
                )

            # 5. Check for test files outside skills
            if filename.startswith("test_") and ext == ".py" and not norm.startswith("skills/"):
                checks.append(
                    CheckResult(
                        check_id="HYGIENE_NO_TEST_FILES",
                        category=CheckCategory.SECRET_HYGIENE,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=norm,
                        expected="Zero unit tests packaged into agent submission root",
                        observed=f"Found test script '{filename}'",
                        diagnostic=f"Development test script '{norm}' packaged in submission. Remove unit tests from submission package.",
                        rule_ref="PLAN.md Stage 47",
                    )
                )


        # 6. Deep content inspection for text files: secrets & host paths
        if ext in (".yaml", ".yml", ".md", ".txt", ".json", ".py"):
            scanned_text_files += 1
            try:
                content = reader.read_text(norm)
            except Exception:
                # Binary or non-UTF8 text file
                continue

            file_has_secret = False
            for sec_name, pattern in SECRET_PATTERNS:
                match = pattern.search(content)
                if match:
                    file_has_secret = True
                    matched_str = match.group(0)
                    redacted = redact_secret_string(matched_str)
                    checks.append(
                        CheckResult(
                            check_id="SECRET_DETECTED",
                            category=CheckCategory.SECRET_HYGIENE,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm,
                            expected="Zero secrets, API keys, or private keys in package files",
                            observed=f"{sec_name} pattern matched ({redacted})",
                            diagnostic=f"Credential violation in '{norm}': {sec_name} detected ({redacted}).",
                            rule_ref=".agents/rules/security.md",
                        )
                    )

            if not file_has_secret:
                clean_secret_files += 1

            # Check for host machine specific absolute paths
            host_match = HOST_PATH_PATTERN.search(content)
            if host_match:
                matched_path = host_match.group(0)
                checks.append(
                    CheckResult(
                        check_id="HYGIENE_HOST_PATH",
                        category=CheckCategory.SECRET_HYGIENE,
                        status=CheckStatus.WARNING,
                        severity=CheckSeverity.WARNING,
                        target=norm,
                        expected="Zero developer machine-specific absolute paths in configuration or prompts",
                        observed=f"Host path pattern matched: '{matched_path}'",
                        diagnostic=f"Developer host path detected in '{norm}': '{matched_path}'. Use relative package paths.",
                        rule_ref="PLAN.md Stage 47",
                    )
                )

    if clean_secret_files > 0 and not any(c.check_id == "SECRET_DETECTED" for c in checks):
        checks.append(
            CheckResult(
                check_id="SECRET_SCAN_CLEAN",
                category=CheckCategory.SECRET_HYGIENE,
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                target="package_contents",
                expected="Zero secrets across all text package members",
                observed=f"{scanned_text_files} text files scanned cleanly",
                diagnostic=f"Zero credentials or private keys detected across {scanned_text_files} text files.",
                rule_ref=".agents/rules/security.md",
            )
        )

    return checks
