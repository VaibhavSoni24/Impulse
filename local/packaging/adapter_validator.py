"""Optional PEFT LoRA adapter directory, config schema, and safetensors header validator."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
import struct
from typing import Optional

from local.packaging.config_validator import normalize_model_name
from local.packaging.constants import MAX_LORA_RANK, PROHIBITED_WEIGHT_EXTENSIONS
from local.packaging.models import (
    CheckCategory,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    ValidatorConfig,
)
from local.packaging.reader import PackageReader, normalize_rel_path


def validate_safetensors_header(header_bytes: bytes) -> tuple[bool, str]:
    """Validates that bytes represent a plausible safetensors file header.
    
    Safetensors format:
    - Bytes 0..8: unsigned 64-bit little-endian integer N (header length in bytes).
    - Bytes 8..8+N: UTF-8 encoded JSON string containing tensor dictionary.
    """
    if len(header_bytes) < 8:
        return False, "File size smaller than 8 bytes minimum header length"
    header_len = struct.unpack("<Q", header_bytes[:8])[0]
    if header_len <= 0 or header_len > 100_000_000:
        return False, f"Plausible header length exceeded: {header_len} bytes"
    if len(header_bytes) < 8 + header_len:
        return False, f"Incomplete safetensors header: expected {8 + header_len} bytes, got {len(header_bytes)}"
    try:
        json_str = header_bytes[8:8 + header_len].decode("utf-8")
        parsed = json.loads(json_str)
        if not isinstance(parsed, dict):
            return False, "Safetensors header JSON is not a dictionary"
        return True, "Valid safetensors header JSON"
    except Exception as e:
        return False, f"Failed to parse safetensors JSON header: {e}"


def validate_adapters(
    reader: PackageReader,
    referenced_adapters: set[str],
    declared_base_model: Optional[str] = None,
    config: Optional[ValidatorConfig] = None,
) -> list[CheckResult]:
    """Validates all PEFT LoRA adapters referenced in agent configurations."""
    checks: list[CheckResult] = []

    if not referenced_adapters:
        checks.append(
            CheckResult(
                check_id="ADAPTER_REFERENCED",
                category=CheckCategory.ADAPTER_PEFT,
                status=CheckStatus.SKIPPED,
                severity=CheckSeverity.INFO,
                target="adapters",
                expected="Adapters validated if referenced in configuration",
                observed="Zero adapters declared (optional PEFT not used)",
                diagnostic="Package declares zero adapters; adapter validation skipped.",
                rule_ref="HARNESS_README.md Section 3.4",
            )
        )
        return checks

    all_entries = set(reader.list_entries())

    for adapter_name in sorted(referenced_adapters):
        # Traversal check in adapter name
        if ".." in adapter_name or "/" in adapter_name or "\\" in adapter_name:
            checks.append(
                CheckResult(
                    check_id="ADAPTER_PATH_TRAVERSAL",
                    category=CheckCategory.ADAPTER_PEFT,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=adapter_name,
                    expected="Adapter name is a clean directory name under adapters/",
                    observed=f"Adapter reference '{adapter_name}' contains slashes or traversal components",
                    diagnostic=f"PathTraversalError: Adapter reference '{adapter_name}' is invalid.",
                    rule_ref="HARNESS_README.md Section 3.4",
                )
            )
            continue

        adapter_dir = f"adapters/{adapter_name}"

        # Check adapter directory exists
        adapter_files = [e for e in all_entries if e.startswith(f"{adapter_dir}/")]
        if not adapter_files:
            checks.append(
                CheckResult(
                    check_id="ADAPTER_DIR_EXISTS",
                    category=CheckCategory.ADAPTER_PEFT,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=adapter_dir,
                    expected=f"Referenced adapter directory '{adapter_dir}' exists in package",
                    observed="Directory not found or empty",
                    diagnostic=f"DanglingAdapterReferenceError: Referenced adapter '{adapter_name}' not found at {adapter_dir}.",
                    rule_ref="HARNESS_README.md Section 3.4",
                )
            )
            continue

        checks.append(
            CheckResult(
                check_id="ADAPTER_DIR_EXISTS",
                category=CheckCategory.ADAPTER_PEFT,
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                target=adapter_dir,
                expected=f"Adapter directory '{adapter_dir}' exists",
                observed="Found adapter directory with member files",
                diagnostic=f"Adapter directory '{adapter_dir}' verified.",
                rule_ref="HARNESS_README.md Section 3.4",
            )
        )

        # Check prohibited weight formats in adapter directory
        for f in adapter_files:
            ext = PurePosixPath(f).suffix.lower()
            if ext in PROHIBITED_WEIGHT_EXTENSIONS:
                checks.append(
                    CheckResult(
                        check_id="ADAPTER_PROHIBITED_WEIGHTS",
                        category=CheckCategory.ADAPTER_PEFT,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=f,
                        expected="No pickle weights (.safetensors only)",
                        observed=f"Disallowed weight format '{ext}'",
                        diagnostic=f"Prohibited pickle weight '{f}' in adapter '{adapter_name}'. Only safetensors is permitted.",
                        rule_ref="HARNESS_README.md Section 2.4",
                    )
                )

        # Check adapter_config.json
        config_path = f"{adapter_dir}/adapter_config.json"
        if not reader.exists(config_path):
            checks.append(
                CheckResult(
                    check_id="ADAPTER_CONFIG_EXISTS",
                    category=CheckCategory.ADAPTER_PEFT,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=config_path,
                    expected=f"'{config_path}' exists in adapter directory",
                    observed="Missing adapter_config.json",
                    diagnostic=f"Adapter '{adapter_name}' missing required 'adapter_config.json'.",
                    rule_ref="HARNESS_README.md Section 3.4",
                )
            )
        else:
            try:
                cfg_text = reader.read_text(config_path)
                cfg_json = json.loads(cfg_text)

                # Validate PEFT schema fields
                peft_type = cfg_json.get("peft_type")
                if str(peft_type).upper() != "LORA":
                    checks.append(
                        CheckResult(
                            check_id="ADAPTER_PEFT_TYPE",
                            category=CheckCategory.ADAPTER_PEFT,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=config_path,
                            expected="peft_type == 'LORA'",
                            observed=f"peft_type: {repr(peft_type)}",
                            diagnostic=f"Invalid peft_type '{peft_type}' in {config_path}; must be 'LORA'.",
                            rule_ref="HARNESS_README.md Section 3.4",
                        )
                    )
                else:
                    checks.append(
                        CheckResult(
                            check_id="ADAPTER_PEFT_TYPE",
                            category=CheckCategory.ADAPTER_PEFT,
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.INFO,
                            target=config_path,
                            expected="peft_type == 'LORA'",
                            observed="peft_type: 'LORA'",
                            diagnostic="PEFT type 'LORA' verified.",
                            rule_ref="HARNESS_README.md Section 3.4",
                        )
                    )

                rank = cfg_json.get("r")
                if rank is None or not isinstance(rank, int) or rank < 1 or rank > MAX_LORA_RANK:
                    checks.append(
                        CheckResult(
                            check_id="ADAPTER_RANK_BOUNDS",
                            category=CheckCategory.ADAPTER_PEFT,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=config_path,
                            expected=f"Adapter rank 'r' in 1..{MAX_LORA_RANK}",
                            observed=f"r: {repr(rank)}",
                            diagnostic=f"Adapter rank r={rank} in {config_path} exceeds maximum permitted rank ({MAX_LORA_RANK}).",
                            rule_ref="HARNESS_README.md Section 3.1 & 3.4",
                        )
                    )
                else:
                    checks.append(
                        CheckResult(
                            check_id="ADAPTER_RANK_BOUNDS",
                            category=CheckCategory.ADAPTER_PEFT,
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.INFO,
                            target=config_path,
                            expected=f"Adapter rank 'r' in 1..{MAX_LORA_RANK}",
                            observed=f"r={rank}",
                            diagnostic=f"Adapter rank r={rank} within bounds (<= {MAX_LORA_RANK}).",
                            rule_ref="HARNESS_README.md Section 3.1",
                        )
                    )

                target_modules = cfg_json.get("target_modules")
                if not target_modules or not isinstance(target_modules, list):
                    checks.append(
                        CheckResult(
                            check_id="ADAPTER_TARGET_MODULES",
                            category=CheckCategory.ADAPTER_PEFT,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=config_path,
                            expected="target_modules is a non-empty list of module names",
                            observed=f"target_modules: {repr(target_modules)}",
                            diagnostic=f"Adapter {config_path} missing valid 'target_modules' list.",
                            rule_ref="HARNESS_README.md Section 3.4",
                        )
                    )

                base_model_ref = cfg_json.get("base_model_name_or_path")
                if declared_base_model and base_model_ref:
                    norm_adapter_model = normalize_model_name(str(base_model_ref))
                    norm_declared = normalize_model_name(declared_base_model)
                    if norm_adapter_model != norm_declared:
                        checks.append(
                            CheckResult(
                                check_id="ADAPTER_BASE_MODEL_MATCH",
                                category=CheckCategory.ADAPTER_PEFT,
                                status=CheckStatus.WARNING,
                                severity=CheckSeverity.WARNING,
                                target=config_path,
                                expected=f"base_model_name_or_path matches declared model '{norm_declared}'",
                                observed=f"base_model_name_or_path: '{base_model_ref}'",
                                diagnostic=(
                                    f"Adapter {config_path} declares base_model_name_or_path '{base_model_ref}' "
                                    f"which differs from package declared base model '{norm_declared}'."
                                ),
                                rule_ref="HARNESS_README.md Section 3.2",
                            )
                        )

            except Exception as e:
                checks.append(
                    CheckResult(
                        check_id="ADAPTER_CONFIG_PARSE",
                        category=CheckCategory.ADAPTER_PEFT,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=config_path,
                        expected="Valid JSON in adapter_config.json",
                        observed=f"Parse error: {e}",
                        diagnostic=f"Failed to parse JSON in '{config_path}': {e}",
                        rule_ref="HARNESS_README.md Section 3.4",
                    )
                )

        # Check adapter_model.safetensors
        weights_path = f"{adapter_dir}/adapter_model.safetensors"
        if not reader.exists(weights_path):
            checks.append(
                CheckResult(
                    check_id="ADAPTER_WEIGHTS_EXISTS",
                    category=CheckCategory.ADAPTER_PEFT,
                    status=CheckStatus.FAIL,
                    severity=CheckSeverity.FATAL,
                    target=weights_path,
                    expected=f"'{weights_path}' exists in adapter directory",
                    observed="Missing adapter_model.safetensors",
                    diagnostic=f"Adapter '{adapter_name}' missing required weights file 'adapter_model.safetensors'.",
                    rule_ref="HARNESS_README.md Section 3.4",
                )
            )
        else:
            try:
                # Read initial 65KB chunk for header inspection without loading full tensor data
                chunk = reader.read_bytes(weights_path)[:65536]
                valid_hdr, msg = validate_safetensors_header(chunk)
                if not valid_hdr:
                    checks.append(
                        CheckResult(
                            check_id="ADAPTER_SAFETENSORS_HEADER",
                            category=CheckCategory.ADAPTER_PEFT,
                            status=CheckStatus.FAIL,
                            severity=CheckSeverity.FATAL,
                            target=weights_path,
                            expected="Valid safetensors uint64 length prefix and JSON header",
                            observed=f"Header check failed: {msg}",
                            diagnostic=f"Corrupt or invalid safetensors header in '{weights_path}': {msg}.",
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )
                else:
                    checks.append(
                        CheckResult(
                            check_id="ADAPTER_SAFETENSORS_HEADER",
                            category=CheckCategory.ADAPTER_PEFT,
                            status=CheckStatus.PASS,
                            severity=CheckSeverity.INFO,
                            target=weights_path,
                            expected="Valid safetensors uint64 length prefix and JSON header",
                            observed="Valid safetensors header confirmed",
                            diagnostic=f"Safetensors weight header verified in '{weights_path}'.",
                            rule_ref="HARNESS_README.md Section 2.4",
                        )
                    )
            except Exception as e:
                checks.append(
                    CheckResult(
                        check_id="ADAPTER_WEIGHTS_READ",
                        category=CheckCategory.ADAPTER_PEFT,
                        status=CheckStatus.FAIL,
                        severity=CheckSeverity.FATAL,
                        target=weights_path,
                        expected="Readable safetensors weights file",
                        observed=f"Read error: {e}",
                        diagnostic=f"Failed to inspect safetensors weights '{weights_path}': {e}",
                        rule_ref="HARNESS_README.md Section 3.4",
                    )
                )

    return checks
