#!/usr/bin/env python3
"""Submission package validator for IMPULSE agent artifacts (directories and ZIP archives).

Supports:
- Candidate directory validation:
    python scripts/validate_submission.py experiments/candidates/M0
- Submission ZIP archive validation:
    python scripts/validate_submission.py path/to/submission.zip
- Machine-readable JSON output:
    python scripts/validate_submission.py path/to/submission.zip --json
- Strict warning mode:
    python scripts/validate_submission.py path/to/submission.zip --strict

Guarantees:
1. Canonical PKZIP archive security, central directory verification, and CRC32 checks.
2. Canonical root entry point discovery (agent.yaml / agent.yml at archive root).
3. Sandboxed !include resolution with cycle, depth (<=10), and traversal detection.
4. Single declared base model rule enforcement across root and sub-agents.
5. Strict schema validation for agents, tools, generation parameters, and sub-agents.
6. Optional PEFT LoRA adapter directory, config schema, and safetensors header verification.
7. Skill manifest (SKILL.md), frontmatter, and static script syntax checking.
8. Secret scanning (zero credentials) with masked reporting and dev-artifact hygiene.
9. 100% read-only mutation safety invariant (hash before == hash after).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Optional

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.packaging.constants import (
    ALLOWED_FILE_EXTENSIONS,
    ALLOWED_MODELS,
    COMPETITION_RULES_SOURCE,
    COMPETITION_RULES_VERIFIED_DATE,
    MAX_AGENTS,
    MAX_FILE_COUNT,
    MAX_INCLUDE_DEPTH,
    MAX_INSTRUCTION_CHARS,
    MAX_LOOP_ITERATIONS,
    MAX_SUB_AGENT_DEPTH,
    MAX_TOTAL_SIZE_BYTES,
    MAX_YAML_FILES,
    MAX_YAML_SIZE_BYTES,
    PREDEFINED_TOOLS,
    PRIMARY_BASE_MODEL,
    PROHIBITED_GENERATE_CONTENT_CONFIG_FIELDS,
    RULESET_VERSION,
    VALID_THINKING_LEVELS,
    VALIDATOR_VERSION,
)
from local.packaging.config_validator import normalize_model_name, parse_simple_yaml
from local.packaging.models import (
    CheckResult,
    CheckStatus,
    PackageValidationResult,
    ValidatorConfig,
)
from local.packaging.validator import PackageValidator


class SubmissionValidator:
    """Backward-compatible validator interface used across IMPULSE scripts and tests."""

    def __init__(self, root_dir: Path | str, strict: bool = False) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.strict = strict
        self.discovered_models: set[str] = set()
        self.total_file_count = 0
        self.total_size_bytes = 0
        self.yaml_file_count = 0
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.last_result: Optional[PackageValidationResult] = None

    def validate(self) -> bool:
        config = ValidatorConfig(strict_mode=self.strict)
        validator = PackageValidator(self.root_dir, config)
        res = validator.validate()
        self.last_result = res
        self.discovered_models = set(res.discovered_models)
        self.total_file_count = res.total_files
        self.total_size_bytes = res.total_size_bytes
        self.yaml_file_count = res.yaml_files

        # Map failures and warnings with actionable diagnostics
        self.errors = [c.diagnostic for c in res.get_failures()]
        self.warnings = [c.diagnostic for c in res.get_warnings()]
        return res.overall_valid


def validate_submission_target(
    target_path: Path | str,
    json_output: bool = False,
    strict: bool = False,
) -> tuple[bool, PackageValidationResult]:
    """Validates target package and prints formatted summary or JSON."""
    target = Path(target_path).resolve()
    config = ValidatorConfig(strict_mode=strict)
    validator = PackageValidator(target, config)
    result = validator.validate()

    if json_output:
        print(result.to_json(indent=2))
        return result.overall_valid, result

    # Format human-readable summary
    target_type_label = "Archive (ZIP)" if result.target_type == "ARCHIVE_ZIP" else "Directory"
    print(f"=== Validating Submission {target_type_label}: {target.name} ===")
    print(f"Target Path:           {target}")
    if result.archive_metadata:
        print(f"Archive SHA-256:       {result.archive_metadata.archive_sha256}")
        print(f"Compressed Size:       {result.archive_metadata.compressed_size:,} bytes ({result.archive_metadata.compressed_size / (1024*1024):.2f} MB)")
        print(f"Central Member Count:  {result.archive_metadata.member_count}")
        print(f"Root Entrypoint:       {result.archive_metadata.root_config_path}")

    print(f"Total Files Inspected: {result.total_files}")
    print(f"Total YAML Files:      {result.yaml_files}")
    print(f"Total Unpacked Size:   {result.total_size_bytes:,} bytes ({result.total_size_bytes / (1024*1024):.2f} MB)")
    print(f"Discovered Models:     {sorted(result.discovered_models)}")

    # Summary counts
    print("\nValidation Summary:")
    print(f"  Checks Executed:     {result.checks_executed}")
    print(f"  Passed:              {result.passed_count}")
    print(f"  Failed:              {result.failed_count}")
    print(f"  Warnings:            {result.warnings_count}")
    print(f"  Skipped:             {result.skipped_count}")
    print(f"  Unavailable:         {result.unavailable_count}")

    warnings = result.get_warnings()
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  [WARN] {w.check_id} ({w.target}): {w.diagnostic}")

    failures = result.get_failures()
    if failures:
        print("\nValidation Errors:")
        for e in failures:
            print(f"  [ERROR] {e.check_id} ({e.target}): {e.diagnostic}")
        print("\nRESULT: FAILED")
    else:
        print("\nRESULT: PASSED (Schema, security, single-model rule, and limits verified)")

    return result.overall_valid, result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate IMPULSE agent submission package (directory or ZIP archive) against competition rules."
    )
    parser.add_argument(
        "submission_path",
        nargs="?",
        default="agent",
        help="Path to submission directory or ZIP archive (default: agent)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in structured machine-readable JSON format",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: treat non-fatal warnings as validation failures",
    )
    args = parser.parse_args()

    success, _ = validate_submission_target(
        args.submission_path,
        json_output=args.json,
        strict=args.strict,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
