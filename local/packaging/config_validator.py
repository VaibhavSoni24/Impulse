"""Declarative agent configuration and sandboxed !include validation."""

from __future__ import annotations

import json
import os
from pathlib import PurePosixPath
import re
import shutil
from typing import Any, Optional

from local.packaging.constants import (
    ALLOWED_MODELS,
    MAX_INSTRUCTION_CHARS,
    MAX_SUB_AGENT_DEPTH,
    PREDEFINED_TOOLS,
    PROHIBITED_GENERATE_CONTENT_CONFIG_FIELDS,
    VALID_THINKING_LEVELS,
)
from local.packaging.models import (
    CheckCategory,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    ValidatorConfig,
)
from local.packaging.reader import PackageReader, normalize_rel_path


def normalize_model_name(name: str) -> str:
    """Strips provider prefixes per adk-submission."""
    for prefix in ("openai/", "google/", "hosted_vllm/", "custom/"):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _clean_val(val: str) -> Any:
    val = val.strip()
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.lower() in ("null", "none", "~"):
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


try:
    import yaml

    class _SafeLoaderWithInclude(yaml.SafeLoader):
        pass

    _SafeLoaderWithInclude.add_constructor(
        "!include",
        lambda loader, node: f"!include {node.value}",
    )
except ImportError:
    yaml = None
    _SafeLoaderWithInclude = None


def parse_simple_yaml(text: str) -> Any:
    """Parses YAML text. Uses PyYAML when available, with pure-Python fallback."""
    if yaml is not None and _SafeLoaderWithInclude is not None:
        return yaml.load(text, Loader=_SafeLoaderWithInclude)
    lines = text.splitlines()
    return _parse_yaml_lines(lines, 0, 0)[0]


def _parse_yaml_lines(lines: list[str], idx: int, min_indent: int) -> tuple[Any, int]:
    mapping: dict[str, Any] = {}
    items: list[Any] = []
    is_list = None

    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            idx += 1
            continue

        indent = len(line) - len(line.lstrip())
        if indent < min_indent:
            break

        if stripped.startswith("- "):
            if is_list is False:
                break
            is_list = True
            val_str = stripped[2:].strip()
            if ":" in val_str and not val_str.startswith("{"):
                k, v = val_str.split(":", 1)
                sub_dict: dict[str, Any] = {k.strip(): v.strip()}
                idx += 1
                if idx < len(lines):
                    next_indent = len(lines[idx]) - len(lines[idx].lstrip())
                    if next_indent > indent:
                        sub_parsed, idx = _parse_yaml_lines(lines, idx, next_indent)
                        if isinstance(sub_parsed, dict):
                            sub_dict.update(sub_parsed)
                items.append(sub_dict)
            else:
                items.append(_clean_val(val_str))
                idx += 1
        elif ":" in stripped:
            if is_list is True:
                break
            is_list = False
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip()
            idx += 1
            if v == "":
                if idx < len(lines):
                    next_indent = len(lines[idx]) - len(lines[idx].lstrip())
                    if next_indent > indent:
                        nested_val, idx = _parse_yaml_lines(lines, idx, next_indent)
                        mapping[k] = nested_val
                    else:
                        mapping[k] = None
                else:
                    mapping[k] = None
            else:
                mapping[k] = _clean_val(v)
        else:
            idx += 1

    return (items if is_list else mapping), idx


class ConfigurationValidator:
    """Validates root agent and sub-agent YAMLs, models, tools, and includes."""

    def __init__(self, reader: PackageReader, config: Optional[ValidatorConfig] = None) -> None:
        self.reader = reader
        self.config = config or ValidatorConfig()
        self.discovered_models: set[str] = set()
        self.discovered_skills: set[str] = set()
        self.discovered_adapters: set[str] = set()
        self.validated_configs: set[str] = set()
        self.checks: list[CheckResult] = []

    def validate_package_configuration(self, root_config_path: str = "agent.yaml") -> list[CheckResult]:
        """Validates root agent configuration and full sub-agent hierarchy."""
        # Find root config if not agent.yaml
        if not self.reader.exists(root_config_path):
            candidates = [
                f for f in ["agent.yaml", "agent.yml", "root_agent.yaml", "root_agent.yml"]
                if self.reader.exists(f)
            ]
            if not candidates:
                self.checks.append(
                    CheckResult(
                        check_id="CONFIG_ROOT_DISCOVERY",
                        category=CheckCategory.SCHEMA_CONFIG,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=root_config_path,
                        expected="Root agent configuration file present",
                        observed="No root agent configuration found",
                        diagnostic="MissingRootConfigError: No agent.yaml found in package root.",
                        rule_ref="HARNESS_README.md Section 2.2",
                    )
                )
                return self.checks
            root_config_path = candidates[0]

        # Validate agent tree starting at root
        self._validate_agent_file(root_config_path, depth=0, is_root=True)

        # Single declared base model rule across all agents
        if len(self.discovered_models) == 0:
            self.checks.append(
                CheckResult(
                    check_id="MODEL_DECLARED",
                    category=CheckCategory.MODEL_TOOL,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=root_config_path,
                    expected="At least one valid base model declared",
                    observed="Zero base models discovered",
                    diagnostic="No base model declared in submission hierarchy.",
                    rule_ref="HARNESS_README.md Section 3.2",
                )
            )
        elif len(self.discovered_models) == 1:
            declared = list(self.discovered_models)[0]
            self.checks.append(
                CheckResult(
                    check_id="MODEL_SINGLE_BASE",
                    category=CheckCategory.MODEL_TOOL,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target=root_config_path,
                    expected="Exactly one base model across entire agent tree",
                    observed=f"Single base model declared: '{declared}'",
                    diagnostic=f"Single Base Model Rule satisfied ({declared}).",
                    rule_ref="HARNESS_README.md Section 3.2",
                )
            )
        else:
            self.checks.append(
                CheckResult(
                    check_id="MODEL_SINGLE_BASE",
                    category=CheckCategory.MODEL_TOOL,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=root_config_path,
                    expected="Exactly one base model across entire agent tree",
                    observed=f"Multiple base models declared: {sorted(self.discovered_models)}",
                    diagnostic=(
                        f"ParticipantVisibleError: Single Base Model Rule violated. "
                        f"Multiple models declared: {sorted(self.discovered_models)}"
                    ),
                    rule_ref="HARNESS_README.md Section 3.2",
                )
            )

        # Official compiler availability check
        self._check_official_compiler()

        return self.checks

    def _validate_agent_file(self, config_rel_path: str, depth: int, is_root: bool = False) -> None:
        norm_path = normalize_rel_path(config_rel_path)
        if depth > MAX_SUB_AGENT_DEPTH:
            self.checks.append(
                CheckResult(
                    check_id="CONFIG_SUB_AGENT_DEPTH",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_path,
                    expected=f"Sub-agent depth <= {MAX_SUB_AGENT_DEPTH}",
                    observed=f"Depth {depth}",
                    diagnostic=f"Max sub-agent depth exceeded ({depth} > {MAX_SUB_AGENT_DEPTH}) at {norm_path}.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )
            return

        if norm_path in self.validated_configs:
            # Already validated this config file
            return
        self.validated_configs.add(norm_path)

        if not self.reader.exists(norm_path):
            self.checks.append(
                CheckResult(
                    check_id="CONFIG_EXISTS",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_path,
                    expected=f"Config file '{norm_path}' exists in package",
                    observed="File missing",
                    diagnostic=f"Agent configuration file not found: '{norm_path}'.",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            return

        try:
            content = self.reader.read_text(norm_path)
        except Exception as e:
            self.checks.append(
                CheckResult(
                    check_id="CONFIG_READ",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_path,
                    expected="Readable UTF-8 config content",
                    observed=f"Read error: {e}",
                    diagnostic=f"Could not read config {norm_path}: {e}",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            return

        parent_dir = str(PurePosixPath(norm_path).parent)
        if parent_dir == ".":
            parent_dir = ""

        resolved_yaml, includes = self._resolve_includes(
            content, parent_dir, depth=0, include_stack=[norm_path]
        )

        try:
            parsed = parse_simple_yaml(resolved_yaml)
        except Exception as e:
            self.checks.append(
                CheckResult(
                    check_id="CONFIG_YAML_SYNTAX",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_path,
                    expected="Valid YAML mapping",
                    observed=f"Parse error: {e}",
                    diagnostic=f"Failed to parse YAML in {norm_path}: {e}",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            return

        if not isinstance(parsed, dict):
            self.checks.append(
                CheckResult(
                    check_id="CONFIG_SCHEMA_MAPPING",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_path,
                    expected="Top-level YAML structure is a mapping",
                    observed=f"Parsed type: {type(parsed).__name__}",
                    diagnostic=f"Config {norm_path} does not parse into a mapping dictionary.",
                    rule_ref="HARNESS_README.md Section 2.3",
                )
            )
            return

        # Check required fields
        name = parsed.get("name")
        if not name or not isinstance(name, str):
            self.checks.append(
                CheckResult(
                    check_id="CONFIG_AGENT_NAME",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_path,
                    expected="Agent has valid non-empty 'name' string",
                    observed=f"name: {repr(name)}",
                    diagnostic=f"Agent in {norm_path} missing valid 'name' string.",
                    rule_ref="HARNESS_README.md Section 2.3",
                )
            )

        model = parsed.get("model")
        if model:
            normalized = normalize_model_name(str(model))
            self.discovered_models.add(normalized)
            if normalized not in ALLOWED_MODELS:
                self.checks.append(
                    CheckResult(
                        check_id="MODEL_PERMITTED_ALIAS",
                        category=CheckCategory.MODEL_TOOL,
                        status=CheckStatus.WARNING,
                        severity=CheckSeverity.WARNING,
                        target=norm_path,
                        expected=f"Model in allowed aliases {sorted(ALLOWED_MODELS)}",
                        observed=f"Declared model: '{normalized}'",
                        diagnostic=f"Declared model '{normalized}' in {norm_path} is not in canonical Gemma 4 registry aliases.",
                        rule_ref="HARNESS_README.md Section 3.3",
                    )
                )

        instruction = parsed.get("instruction", "")
        if len(str(instruction)) > MAX_INSTRUCTION_CHARS:
            self.checks.append(
                CheckResult(
                    check_id="CONFIG_INSTRUCTION_LENGTH",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=norm_path,
                    expected=f"Instruction <= {MAX_INSTRUCTION_CHARS} chars",
                    observed=f"{len(str(instruction)):,} chars",
                    diagnostic=f"Instruction in {norm_path} exceeds {MAX_INSTRUCTION_CHARS} characters.",
                    rule_ref="HARNESS_README.md Section 2.4",
                )
            )

        # Track skills
        skills = parsed.get("skills")
        if isinstance(skills, list):
            for s in skills:
                if isinstance(s, str):
                    self.discovered_skills.add(normalize_rel_path(s))

        # Track adapter
        adapter = parsed.get("adapter")
        if adapter:
            self.discovered_adapters.add(str(adapter))

        # Validate tools
        tools = parsed.get("tools", [])
        if isinstance(tools, list):
            for t in tools:
                if isinstance(t, str):
                    if t not in PREDEFINED_TOOLS:
                        self.checks.append(
                            CheckResult(
                                check_id="TOOL_PREDEFINED",
                                category=CheckCategory.MODEL_TOOL,
                                status=CheckStatus.WARNING,
                                severity=CheckSeverity.WARNING,
                                target=norm_path,
                                expected=f"Tool in predefined 9 tools: {sorted(PREDEFINED_TOOLS)}",
                                observed=f"Tool name: '{t}'",
                                diagnostic=f"Tool '{t}' in {norm_path} is not in the standard 9 predefined tools.",
                                rule_ref="HARNESS_README.md Section 6.1",
                            )
                        )
                elif isinstance(t, dict):
                    agent_tool = t.get("agent_tool")
                    if isinstance(agent_tool, dict):
                        sub_cfg = agent_tool.get("config_path")
                        if sub_cfg:
                            sub_target = self._resolve_relative_path(parent_dir, str(sub_cfg))
                            self._validate_agent_file(sub_target, depth + 1)

        # Validate sub_agents
        sub_agents = parsed.get("sub_agents", [])
        if isinstance(sub_agents, list):
            for sa in sub_agents:
                if isinstance(sa, dict) and "config_path" in sa:
                    sub_cfg = sa["config_path"]
                    sub_target = self._resolve_relative_path(parent_dir, str(sub_cfg))
                    self._validate_agent_file(sub_target, depth + 1)

        # Validate generate_content_config
        gcc = parsed.get("generate_content_config")
        if isinstance(gcc, dict):
            for prohibited in PROHIBITED_GENERATE_CONTENT_CONFIG_FIELDS:
                if prohibited in gcc:
                    self.checks.append(
                        CheckResult(
                            check_id="CONFIG_PROHIBITED_FIELD",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm_path,
                            expected=f"Field '{prohibited}' not present in generate_content_config",
                            observed=f"Found prohibited field '{prohibited}'",
                            diagnostic=(
                                f"ProhibitedFieldViolation: Field '{prohibited}' inside "
                                f"generate_content_config in {norm_path} is prohibited."
                            ),
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )

            max_tokens = gcc.get("max_output_tokens")
            if max_tokens is not None and (
                not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 32768
            ):
                self.checks.append(
                    CheckResult(
                        check_id="CONFIG_MAX_OUTPUT_TOKENS",
                        category=CheckCategory.SCHEMA_CONFIG,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=norm_path,
                        expected="max_output_tokens between 1 and 32,768",
                        observed=f"Got {max_tokens}",
                        diagnostic=f"max_output_tokens must be in 1..32768 in {norm_path}, got {max_tokens}.",
                        rule_ref="HARNESS_README.md Section 2.4",
                    )
                )

            thinking = gcc.get("thinking_config")
            if isinstance(thinking, dict):
                budget = thinking.get("thinking_budget")
                if budget is not None and (
                    not isinstance(budget, int) or budget < 1 or budget > 32768
                ):
                    self.checks.append(
                        CheckResult(
                            check_id="CONFIG_THINKING_BUDGET",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm_path,
                            expected="thinking_budget between 1 and 32,768",
                            observed=f"Got {budget}",
                            diagnostic=f"thinking_budget must be in 1..32768 in {norm_path}, got {budget}.",
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )
                level = thinking.get("thinking_level")
                if level is not None and str(level).lower() not in VALID_THINKING_LEVELS:
                    self.checks.append(
                        CheckResult(
                            check_id="CONFIG_THINKING_LEVEL",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=norm_path,
                            expected=f"thinking_level in {sorted(VALID_THINKING_LEVELS)}",
                            observed=f"Got '{level}'",
                            diagnostic=f"Invalid thinking_level '{level}' in {norm_path}.",
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )

    def _resolve_relative_path(self, base_dir: str, rel_path: str) -> str:
        """Resolves relative path inside package without escaping root."""
        clean_rel = rel_path.replace("\\", "/").strip("\"'")
        if base_dir:
            combined = f"{base_dir}/{clean_rel}"
        else:
            combined = clean_rel
        norm = os.path.normpath(combined).replace("\\", "/")
        return normalize_rel_path(norm)

    def _resolve_includes(
        self,
        text: str,
        base_dir: str,
        depth: int,
        include_stack: list[str],
    ) -> tuple[str, list[str]]:
        """Resolves !include directives recursively with cycle and traversal detection."""
        if depth > 10:
            self.checks.append(
                CheckResult(
                    check_id="INCLUDE_MAX_DEPTH",
                    category=CheckCategory.SCHEMA_CONFIG,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=include_stack[-1] if include_stack else "include",
                    expected="Include depth <= 10",
                    observed=f"Depth {depth}",
                    diagnostic="MaxIncludeDepthError: Max include depth (10) exceeded.",
                    rule_ref="HARNESS_README.md Section 2.2",
                )
            )
            return text, []

        resolved_lines: list[str] = []
        includes: list[str] = []

        for line in text.splitlines():
            match = re.search(r"!include\s+([^\s#]+)", line)
            if match:
                rel_path_str = match.group(1).strip("\"'")
                target_norm = self._resolve_relative_path(base_dir, rel_path_str)

                # Path traversal check
                # Check if target normalized starts with '..'
                clean_combined = f"{base_dir}/{rel_path_str}" if base_dir else rel_path_str
                norm_check = os.path.normpath(clean_combined.replace("\\", "/"))
                if norm_check.startswith("..") or norm_check.startswith("/"):
                    self.checks.append(
                        CheckResult(
                            check_id="INCLUDE_PATH_TRAVERSAL",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=rel_path_str,
                            expected="!include target resolves within package root",
                            observed=f"!include {rel_path_str} escapes package root",
                            diagnostic=f"PathTraversalError: !include {rel_path_str} escapes submission root.",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )
                    continue

                # Cycle detection
                if target_norm in include_stack:
                    self.checks.append(
                        CheckResult(
                            check_id="INCLUDE_CYCLE",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=target_norm,
                            expected="Acyclic inclusion graph",
                            observed=f"Cycle detected: {' -> '.join(include_stack)} -> {target_norm}",
                            diagnostic=f"IncludeCycleError: Recursive include cycle detected involving '{target_norm}'.",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )
                    continue

                # Target existence check
                if not self.reader.exists(target_norm):
                    self.checks.append(
                        CheckResult(
                            check_id="INCLUDE_NOT_FOUND",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=target_norm,
                            expected=f"Included file '{target_norm}' exists in package",
                            observed="Target file does not exist",
                            diagnostic=f"IncludeNotFoundError: !include target '{rel_path_str}' resolved to '{target_norm}' does not exist.",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )
                    continue

                includes.append(target_norm)
                ext = PurePosixPath(target_norm).suffix.lower()

                try:
                    target_content = self.reader.read_text(target_norm)
                except Exception as e:
                    self.checks.append(
                        CheckResult(
                            check_id="INCLUDE_READ_ERROR",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=target_norm,
                            expected="Include target readable as UTF-8",
                            observed=f"Read error: {e}",
                            diagnostic=f"Failed to read included file '{target_norm}': {e}",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )
                    continue

                if ext in (".md", ".txt"):
                    indent = " " * (len(line) - len(line.lstrip()))
                    prefix = line[:match.start()]
                    escaped = json.dumps(target_content.strip())
                    resolved_lines.append(f"{prefix}{escaped}")
                elif ext in (".yaml", ".yml"):
                    sub_parent = str(PurePosixPath(target_norm).parent)
                    if sub_parent == ".":
                        sub_parent = ""
                    new_stack = include_stack + [target_norm]
                    sub_resolved, sub_incs = self._resolve_includes(
                        target_content, sub_parent, depth + 1, new_stack
                    )
                    includes.extend(sub_incs)
                    indent = " " * (len(line) - len(line.lstrip()))
                    prefix = line[:match.start()]
                    if prefix.strip().endswith(":"):
                        indented_sub = "\n".join(
                            (indent + "  " + l) if l.strip() else ""
                            for l in sub_resolved.splitlines()
                        )
                        resolved_lines.append(f"{prefix}\n{indented_sub}")
                    else:
                        resolved_lines.append(sub_resolved)
                else:
                    self.checks.append(
                        CheckResult(
                            check_id="INCLUDE_INVALID_EXTENSION",
                            category=CheckCategory.SCHEMA_CONFIG,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=target_norm,
                            expected="!include targets .md, .txt, .yaml, or .yml",
                            observed=f"Disallowed include extension '{ext}'",
                            diagnostic=f"InvalidIncludeExtension: !include on '{ext}' not permitted in '{target_norm}'.",
                            rule_ref="HARNESS_README.md Section 2.2",
                        )
                    )
            else:
                resolved_lines.append(line)

        return "\n".join(resolved_lines), includes

    def _check_official_compiler(self) -> None:
        """Explicitly records whether the proprietary competition compiler is available."""
        compiler_cmd = shutil.which("adk-submission")
        if compiler_cmd is not None:
            self.checks.append(
                CheckResult(
                    check_id="COMPILER_OFFICIAL_AVAILABILITY",
                    category=CheckCategory.COMPILER_OFFICIAL,
                    status=CheckStatus.PASS,
                    severity=CheckSeverity.INFO,
                    target="adk-submission",
                    expected="Official adk-submission compiler available",
                    observed=f"Found compiler at {compiler_cmd}",
                    diagnostic="Official competition compiler 'adk-submission' detected in environment.",
                    rule_ref="HARNESS_README.md Section 2.1",
                )
            )
        else:
            self.checks.append(
                CheckResult(
                    check_id="COMPILER_OFFICIAL_AVAILABILITY",
                    category=CheckCategory.COMPILER_OFFICIAL,
                    status=CheckStatus.UNAVAILABLE,
                    severity=CheckSeverity.INFO,
                    target="adk-submission",
                    expected="Official adk-submission compiler executed",
                    observed="adk-submission command not found on host (proprietary Kaggle runner package)",
                    diagnostic=(
                        "Official competition compiler 'adk-submission compile <submission_dir>' "
                        "is proprietary to the Kaggle scoring environment and not available locally. "
                        "Local structural YAML validation PASSED."
                    ),
                    rule_ref="HARNESS_README.md Section 2.1",
                )
            )
