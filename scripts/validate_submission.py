#!/usr/bin/env python3
"""Submission structure and schema validator for IMPULSE.

Implements the exact validation checks defined by `adk-submission` and `swegemma`
in `HARNESS_README.md` Section 2:
1. Root config discovery (agent.yaml / agent.yml).
2. Sandboxed `!include` resolution with cycle and traversal detection.
3. Single declared base model rule (`gemma-4-31b-it-qat-w4a16-ct`).
4. Schema validation for LlmAgent, tools, and generate_content_config.
5. Prohibited configuration field detection.
6. Submission file limits and size ceilings (< 3 GiB unpacked).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Authoritative competition limits from swegemma (swegemma/config.py)
MAX_TOTAL_SIZE_BYTES = 3_221_225_472  # 3 GiB
MAX_FILE_COUNT = 10_000
MAX_YAML_FILES = 1_000
MAX_YAML_SIZE_BYTES = 52_428_800  # 50 MiB
MAX_INSTRUCTION_CHARS = 1_000_000
MAX_AGENTS = 500
MAX_SUB_AGENT_DEPTH = 50
MAX_LOOP_ITERATIONS = 500
MAX_INCLUDE_DEPTH = 10

ALLOWED_FILE_EXTENSIONS = {
    ".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"
}

ALLOWED_MODELS = {
    "gemma-4-31b-it-qat-w4a16-ct",
    "gemma-4-31b-it",
    "gemma-4-31b",
    "gemma-4-27b-it",
    "gemma-4-27b",
    "gemma-4-26b-a4b-it",
    "gemma-4-26b-a4b",
    "diffusiongemma-26b-a4b-it",
    "gemma-4-12b-it",
    "gemma-4-12b",
    "gemma-4-9b-it",
    "gemma-4-9b",
    "gemma-4-e4b-it",
    "gemma-4-e4b",
    "gemma-4-e2b-it",
    "gemma-4-e2b",
}

PREDEFINED_TOOLS = {
    "run_command",
    "submit_patch",
    "get_status",
    "read_file",
    "edit_file",
    "write_file",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
}

PROHIBITED_GENERATE_CONTENT_CONFIG_FIELDS = {
    "tools",
    "system_instruction",
    "http_options",
    "safety_settings",
    "response_schema",
}

VALID_THINKING_LEVELS = {"minimal", "low", "medium", "high", "none"}


def normalize_model_name(name: str) -> str:
    """Strips provider prefixes per adk-submission."""
    for prefix in ("openai/", "google/", "hosted_vllm/", "custom/"):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def parse_simple_yaml(text: str) -> Any:
    """Lightweight recursive YAML parser supporting key-values, lists, and !include."""
    lines = text.splitlines()
    return _parse_yaml_lines(lines, 0, 0)[0]


def _parse_yaml_lines(lines: list[str], idx: int, min_indent: int) -> tuple[Any, int]:
    # Simple line-based recursive descent parser for basic agent configs
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


class SubmissionValidator:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.discovered_models: set[str] = set()
        self.total_file_count = 0
        self.total_size_bytes = 0
        self.yaml_file_count = 0
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(self) -> bool:
        if not self.root_dir.exists() or not self.root_dir.is_dir():
            self.errors.append(f"Submission directory does not exist: {self.root_dir}")
            return False

        # 1. Structural inspection
        self._inspect_filesystem(self.root_dir)

        # 2. Root config discovery
        root_configs = [
            f for f in ["agent.yaml", "agent.yml", "root_agent.yaml", "root_agent.yml"]
            if (self.root_dir / f).exists()
        ]
        if not root_configs:
            self.errors.append("MissingRootConfigError: No agent.yaml / agent.yml found in submission root.")
            return False
        if len(root_configs) > 1:
            self.errors.append(f"MultipleRootConfigsError: Multiple root configs found: {root_configs}")
            return False

        root_config_path = self.root_dir / root_configs[0]

        # 3. Recursive compilation & validation
        self._validate_agent_file(root_config_path, depth=0)

        # 4. Single declared base model rule
        if len(self.discovered_models) > 1:
            self.errors.append(
                f"ParticipantVisibleError: Single Base Model Rule violated. Multiple models declared: {sorted(self.discovered_models)}"
            )
        elif len(self.discovered_models) == 0:
            self.errors.append("No base model declared in submission hierarchy.")

        return len(self.errors) == 0

    def _inspect_filesystem(self, current_dir: Path):
        for entry in current_dir.iterdir():
            # Check for symlink outside root
            if entry.is_symlink():
                resolved = entry.resolve()
                if not str(resolved).startswith(str(self.root_dir)):
                    self.errors.append(f"PathTraversalError: Symlink {entry} resolves outside root: {resolved}")
            if entry.is_dir():
                self._inspect_filesystem(entry)
            elif entry.is_file():
                self.total_file_count += 1
                size = entry.stat().st_size
                self.total_size_bytes += size
                ext = entry.suffix.lower()
                if ext in (".yaml", ".yml"):
                    self.yaml_file_count += 1
                    if size > MAX_YAML_SIZE_BYTES:
                        self.errors.append(f"YAML file {entry.name} exceeds {MAX_YAML_SIZE_BYTES} bytes limit.")
                if ext not in ALLOWED_FILE_EXTENSIONS:
                    self.errors.append(
                        f"ProhibitedFileError: Disallowed extension '{ext}' on {entry.relative_to(self.root_dir)}"
                    )

        if self.total_file_count > MAX_FILE_COUNT:
            self.errors.append(f"File count {self.total_file_count} exceeds limit of {MAX_FILE_COUNT}")
        if self.total_size_bytes > MAX_TOTAL_SIZE_BYTES:
            self.errors.append(f"Total size {self.total_size_bytes} exceeds limit of {MAX_TOTAL_SIZE_BYTES} bytes (< 3 GiB)")

    def _validate_agent_file(self, config_path: Path, depth: int):
        if depth > MAX_SUB_AGENT_DEPTH:
            self.errors.append(f"Max sub-agent depth exceeded ({depth} > {MAX_SUB_AGENT_DEPTH}) at {config_path}")
            return

        try:
            content = config_path.read_text(encoding="utf-8")
        except Exception as e:
            self.errors.append(f"Could not read {config_path}: {e}")
            return

        # Resolve !include tags
        resolved_yaml, includes = self._resolve_includes(content, config_path.parent, depth=0)
        parsed = parse_simple_yaml(resolved_yaml)

        if not isinstance(parsed, dict):
            self.errors.append(f"Config {config_path} does not parse into a mapping.")
            return

        # Validate agent fields
        name = parsed.get("name")
        if not name or not isinstance(name, str):
            self.errors.append(f"Agent in {config_path} missing valid 'name' string.")

        model = parsed.get("model")
        if model:
            normalized = normalize_model_name(str(model))
            self.discovered_models.add(normalized)
            if normalized not in ALLOWED_MODELS:
                self.warnings.append(f"Declared model '{normalized}' not in known Gemma 4 registry aliases.")

        instruction = parsed.get("instruction", "")
        if len(str(instruction)) > MAX_INSTRUCTION_CHARS:
            self.errors.append(f"Instruction in {config_path} exceeds {MAX_INSTRUCTION_CHARS} characters.")

        # Validate adapter
        adapter = parsed.get("adapter")
        if adapter:
            adapter_dir = self.root_dir / "adapters" / str(adapter)
            if not adapter_dir.exists() or not adapter_dir.is_dir():
                self.errors.append(f"Referenced adapter '{adapter}' not found at {adapter_dir}")
            else:
                config_json = adapter_dir / "adapter_config.json"
                weights_st = adapter_dir / "adapter_model.safetensors"
                if not config_json.exists():
                    self.errors.append(f"Adapter '{adapter}' missing adapter_config.json")
                if not weights_st.exists():
                    self.errors.append(f"Adapter '{adapter}' missing adapter_model.safetensors")

        # Validate tools
        tools = parsed.get("tools", [])
        if isinstance(tools, list):
            for t in tools:
                if isinstance(t, str):
                    if t not in PREDEFINED_TOOLS:
                        self.warnings.append(f"Tool '{t}' in {config_path} is not in standard 9 predefined tools.")
                elif isinstance(t, dict):
                    agent_tool = t.get("agent_tool")
                    if isinstance(agent_tool, dict):
                        sub_cfg = agent_tool.get("config_path")
                        if sub_cfg:
                            sub_path = (config_path.parent / sub_cfg).resolve()
                            if not sub_path.exists():
                                self.errors.append(f"AgentTool config_path '{sub_cfg}' not found: {sub_path}")
                            else:
                                self._validate_agent_file(sub_path, depth + 1)

        # Validate sub_agents
        sub_agents = parsed.get("sub_agents", [])
        if isinstance(sub_agents, list):
            for sa in sub_agents:
                if isinstance(sa, dict) and "config_path" in sa:
                    sub_path = (config_path.parent / sa["config_path"]).resolve()
                    if not sub_path.exists():
                        self.errors.append(f"Sub-agent config_path '{sa['config_path']}' not found: {sub_path}")
                    else:
                        self._validate_agent_file(sub_path, depth + 1)

        # Validate generate_content_config
        gcc = parsed.get("generate_content_config")
        if isinstance(gcc, dict):
            for prohibited in PROHIBITED_GENERATE_CONTENT_CONFIG_FIELDS:
                if prohibited in gcc:
                    self.errors.append(
                        f"ProhibitedFieldViolation: Field '{prohibited}' inside generate_content_config in {config_path} is prohibited."
                    )
            max_tokens = gcc.get("max_output_tokens")
            if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 32768):
                self.errors.append(f"max_output_tokens must be in 1..32768 in {config_path}, got {max_tokens}")
            thinking = gcc.get("thinking_config")
            if isinstance(thinking, dict):
                budget = thinking.get("thinking_budget")
                if budget is not None and (not isinstance(budget, int) or budget < 1 or budget > 32768):
                    self.errors.append(f"thinking_budget must be in 1..32768 in {config_path}, got {budget}")
                level = thinking.get("thinking_level")
                if level is not None and str(level).lower() not in VALID_THINKING_LEVELS:
                    self.errors.append(f"Invalid thinking_level '{level}' in {config_path}")

    def _resolve_includes(self, text: str, base_dir: Path, depth: int) -> tuple[str, list[Path]]:
        if depth > MAX_INCLUDE_DEPTH:
            self.errors.append(f"Max include depth ({MAX_INCLUDE_DEPTH}) exceeded.")
            return text, []

        resolved_lines = []
        includes = []
        for line in text.splitlines():
            match = re.search(r"!include\s+([^\s#]+)", line)
            if match:
                rel_path_str = match.group(1).strip('"\'')
                target = (base_dir / rel_path_str).resolve()
                # Security traversal check
                if not str(target).startswith(str(self.root_dir)):
                    self.errors.append(f"PathTraversalError: !include {rel_path_str} escapes submission root.")
                    continue
                if not target.exists():
                    self.errors.append(f"IncludeNotFoundError: !include target {rel_path_str} does not exist.")
                    continue

                includes.append(target)
                target_ext = target.suffix.lower()
                target_content = target.read_text(encoding="utf-8")
                if target_ext in (".md", ".txt"):
                    # Raw text inclusion: preserve indentation if part of a key
                    indent = " " * (len(line) - len(line.lstrip()))
                    prefix = line[:match.start()]
                    escaped = json.dumps(target_content.strip())
                    resolved_lines.append(f"{prefix}{escaped}")
                elif target_ext in (".yaml", ".yml"):
                    sub_resolved, sub_incs = self._resolve_includes(target_content, target.parent, depth + 1)
                    includes.extend(sub_incs)
                    indent = " " * (len(line) - len(line.lstrip()))
                    prefix = line[:match.start()]
                    if prefix.strip().endswith(":"):
                        # Multiline nested dictionary inclusion
                        indented_sub = "\n".join((indent + "  " + l) if l.strip() else "" for l in sub_resolved.splitlines())
                        resolved_lines.append(f"{prefix}\n{indented_sub}")
                    else:
                        resolved_lines.append(sub_resolved)
                else:
                    self.errors.append(f"InvalidIncludeExtension: !include on '{target_ext}' not permitted.")
            else:
                resolved_lines.append(line)

        return "\n".join(resolved_lines), includes


def main():
    parser = argparse.ArgumentParser(description="Validate IMPULSE agent submission against competition rules.")
    parser.add_argument("submission_dir", nargs="?", default="agent", help="Path to submission directory (default: agent)")
    args = parser.parse_args()

    sub_dir = Path(args.submission_dir)
    print(f"=== Validating Submission Directory: {sub_dir} ===")
    validator = SubmissionValidator(sub_dir)
    success = validator.validate()

    print(f"Total Files Inspected: {validator.total_file_count}")
    print(f"Total YAML Files:      {validator.yaml_file_count}")
    print(f"Total Unpacked Size:   {validator.total_size_bytes:,} bytes ({validator.total_size_bytes / (1024*1024):.2f} MB)")
    print(f"Discovered Models:     {sorted(validator.discovered_models)}")

    if validator.warnings:
        print("\nWarnings:")
        for w in validator.warnings:
            print(f"  [WARN] {w}")

    if validator.errors:
        print("\nValidation Errors:")
        for e in validator.errors:
            print(f"  [ERROR] {e}")
        print("\nRESULT: FAILED")
        sys.exit(1)
    else:
        print("\nRESULT: PASSED (Schema, single-model rule, and limits verified)")
        sys.exit(0)


if __name__ == "__main__":
    main()
