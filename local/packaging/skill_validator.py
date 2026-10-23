"""ADK Skill directory, manifest, and script syntax validator."""

from __future__ import annotations

import ast
from pathlib import PurePosixPath
import re
from typing import Optional

from local.packaging.config_validator import parse_simple_yaml
from local.packaging.constants import MAX_SKILL_SIZE_BYTES
from local.packaging.models import (
    CheckCategory,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    ValidatorConfig,
)
from local.packaging.reader import PackageReader, normalize_rel_path

FRONTMATTER_REGEX = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def extract_frontmatter(text: str) -> tuple[Optional[str], str]:
    """Extracts YAML frontmatter string and remaining markdown body."""
    match = FRONTMATTER_REGEX.match(text)
    if match:
        return match.group(1), text[match.end():]
    return None, text


def validate_skills(
    reader: PackageReader,
    referenced_skills: set[str],
    config: Optional[ValidatorConfig] = None,
) -> list[CheckResult]:
    """Validates all skill directories referenced in agent configurations."""
    checks: list[CheckResult] = []

    if not referenced_skills:
        checks.append(
            CheckResult(
                check_id="SKILLS_REFERENCED",
                category=CheckCategory.SKILL_MANIFEST,
                status=CheckStatus.SKIPPED,
                severity=CheckSeverity.INFO,
                target="skills",
                expected="Skills validated if referenced in configuration",
                observed="No skills referenced in package",
                diagnostic="Package declares zero skills; skill validation skipped.",
                rule_ref="HARNESS_README.md Section 2.2",
            )
        )
        return checks

    all_entries = set(reader.list_entries())

    for skill_ref in sorted(referenced_skills):
        norm_skill = normalize_rel_path(skill_ref).rstrip("/")

        # Check skill directory exists (must have at least one file prefixed with norm_skill/)
        skill_files = [e for e in all_entries if e == norm_skill or e.startswith(f"{norm_skill}/")]
        if not skill_files:
            checks.append(
                CheckResult(
                    check_id="SKILL_DIR_EXISTS",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_skill,
                    expected=f"Referenced skill directory '{norm_skill}' exists in package",
                    observed="Directory not found",
                    diagnostic=f"Referenced skill directory '{norm_skill}' does not exist in submission package.",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            continue

        # Check total skill directory size <= 50 MiB
        skill_size = sum(reader.file_size(f) for f in skill_files)
        if skill_size > MAX_SKILL_SIZE_BYTES:
            checks.append(
                CheckResult(
                    check_id="SKILL_MAX_SIZE",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_skill,
                    expected=f"Skill directory size <= {MAX_SKILL_SIZE_BYTES:,} bytes (50 MiB)",
                    observed=f"{skill_size:,} bytes",
                    diagnostic=f"Skill '{norm_skill}' exceeds maximum skill size limit ({skill_size:,} > {MAX_SKILL_SIZE_BYTES:,}).",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )
        else:
            checks.append(
                CheckResult(
                    check_id="SKILL_MAX_SIZE",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target=norm_skill,
                    expected=f"Skill directory size <= {MAX_SKILL_SIZE_BYTES:,} bytes",
                    observed=f"{skill_size:,} bytes",
                    diagnostic=f"Skill '{norm_skill}' size ({skill_size:,} bytes) within limit.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )

        # Check SKILL.md exists
        skill_md_path = f"{norm_skill}/SKILL.md"
        if not reader.exists(skill_md_path):
            checks.append(
                CheckResult(
                    check_id="SKILL_MD_EXISTS",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=skill_md_path,
                    expected=f"Manifest '{skill_md_path}' exists in skill directory",
                    observed="SKILL.md missing",
                    diagnostic=f"Skill '{norm_skill}' is missing required manifest 'SKILL.md'.",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            continue

        checks.append(
            CheckResult(
                check_id="SKILL_MD_EXISTS",
                category=CheckCategory.SKILL_MANIFEST,
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                target=skill_md_path,
                expected="SKILL.md manifest exists",
                observed="SKILL.md found",
                diagnostic=f"Skill manifest '{skill_md_path}' found.",
                rule_ref="HARNESS_README.md Section 2.2",
            )
        )

        # Read and parse SKILL.md frontmatter
        try:
            content = reader.read_text(skill_md_path)
        except Exception as e:
            checks.append(
                CheckResult(
                    check_id="SKILL_MD_READ",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=skill_md_path,
                    expected="SKILL.md readable as UTF-8",
                    observed=f"Read error: {e}",
                    diagnostic=f"Failed to read '{skill_md_path}': {e}",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            continue

        frontmatter_str, body = extract_frontmatter(content)
        if not frontmatter_str:
            checks.append(
                CheckResult(
                    check_id="SKILL_FRONTMATTER_EXISTS",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=skill_md_path,
                    expected="SKILL.md contains YAML frontmatter delimited by '---'",
                    observed="No YAML frontmatter found",
                    diagnostic=f"Skill manifest '{skill_md_path}' is missing YAML frontmatter ('---').",
                    rule_ref="PLAN.md Stage 47",
                )
            )
            continue

        try:
            frontmatter = parse_simple_yaml(frontmatter_str)
        except Exception as e:
            checks.append(
                CheckResult(
                    check_id="SKILL_FRONTMATTER_PARSE",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=skill_md_path,
                    expected="YAML frontmatter parses into a dictionary",
                    observed=f"Parse error: {e}",
                    diagnostic=f"Failed to parse YAML frontmatter in '{skill_md_path}': {e}",
                    rule_ref="PLAN.md Stage 47",
                )
            )
            continue

        if not isinstance(frontmatter, dict):
            checks.append(
                CheckResult(
                    check_id="SKILL_FRONTMATTER_SCHEMA",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=skill_md_path,
                    expected="Frontmatter parses as a key-value mapping",
                    observed=f"Parsed type: {type(frontmatter).__name__}",
                    diagnostic=f"Frontmatter in '{skill_md_path}' must be a YAML mapping.",
                    rule_ref="PLAN.md Stage 47",
                )
            )
            continue

        name = frontmatter.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            checks.append(
                CheckResult(
                    check_id="SKILL_MANIFEST_NAME",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=skill_md_path,
                    expected="Frontmatter contains non-empty 'name' string",
                    observed=f"name: {repr(name)}",
                    diagnostic=f"Skill manifest in '{skill_md_path}' missing required non-empty 'name' field.",
                    rule_ref="PLAN.md Stage 47",
                )
            )
        else:
            checks.append(
                CheckResult(
                    check_id="SKILL_MANIFEST_NAME",
                    category=CheckCategory.SKILL_MANIFEST,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target=skill_md_path,
                    expected="Frontmatter contains non-empty 'name' string",
                    observed=f"name: '{name}'",
                    diagnostic=f"Skill manifest name '{name}' verified.",
                    rule_ref="PLAN.md Stage 47",
                )
            )

        # Static Python script syntax validation for scripts in skill
        for f in skill_files:
            if f.endswith(".py"):
                try:
                    py_code = reader.read_text(f)
                    ast.parse(py_code, filename=f)
                    checks.append(
                        CheckResult(
                            check_id="SKILL_SCRIPT_SYNTAX",
                            category=CheckCategory.SKILL_MANIFEST,
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.INFO,
                            target=f,
                            expected="Python script parses with valid syntax",
                            observed="AST parse succeeded (0 execution)",
                            diagnostic=f"Skill script '{f}' syntax verified statically without execution.",
                            rule_ref="PLAN.md Stage 47",
                        )
                    )
                except SyntaxError as e:
                    checks.append(
                        CheckResult(
                            check_id="SKILL_SCRIPT_SYNTAX",
                            category=CheckCategory.SKILL_MANIFEST,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=f,
                            expected="Valid Python script syntax",
                            observed=f"SyntaxError at line {e.lineno}: {e.msg}",
                            diagnostic=f"SyntaxError in skill script '{f}' at line {e.lineno}: {e.msg}.",
                            rule_ref="PLAN.md Stage 47",
                        )
                    )
                except Exception as e:
                    checks.append(
                        CheckResult(
                            check_id="SKILL_SCRIPT_SYNTAX",
                            category=CheckCategory.SKILL_MANIFEST,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=f,
                            expected="Readable Python script",
                            observed=f"Error: {e}",
                            diagnostic=f"Could not inspect skill script '{f}': {e}",
                            rule_ref="PLAN.md Stage 47",
                        )
                    )

    return checks
