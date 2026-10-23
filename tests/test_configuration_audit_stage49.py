"""IMPULSE Submission Configuration Audit & Model Policy Test Suite (Stage 49).

Verifies submission configuration auditing, strict enforcement of the four
official Gemma 4 competition variants announced by Kaggle staff:
  1. gemma-4-31b-it-qat-w4a16-ct
  2. gemma-4-12b-it-qat-w4a16-ct
  3. gemma-4-e4b-it-qat-w4a16-ct
  4. gemma-4-e2b-it-qat-w4a16-ct

Proves single-base-model consistency across root and sub-agents, rejection of
mixed or unapproved variants, malformed sub-agent and tool specs, parity between
directory and ZIP inspection, JSON output diagnostics, and intra-host determinism.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from local.packaging.constants import (
    ALLOWED_MODELS,
    PRIMARY_BASE_MODEL,
)
from local.packaging.models import (
    CheckCategory,
    CheckSeverity,
    CheckStatus,
    PackageValidationResult,
    PackagerConfig,
    ValidatorConfig,
)
from local.packaging.packager import SubmissionPackager
from local.packaging.validator import PackageValidator


class Stage49TestBase(unittest.TestCase):
    """Base test fixture providing isolated temporary directory structures."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="impulse_stage49_test_")
        self.source_dir = Path(self.temp_dir) / "source_pkg"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        (self.source_dir / "prompts").mkdir(parents=True, exist_ok=True)
        (self.source_dir / "sub_agents").mkdir(parents=True, exist_ok=True)
        (self.source_dir / "skills").mkdir(parents=True, exist_ok=True)

        # Baseline valid root prompt
        (self.source_dir / "prompts" / "root.md").write_text(
            "# Root Agent Instructions\nInvestigate and resolve repository issue.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def write_agent_yaml(self, content: str, rel_path: str = "agent.yaml") -> Path:
        target = self.source_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def make_zip_from_source(self, zip_filename: str = "submission.zip") -> Path:
        zip_path = Path(self.temp_dir) / zip_filename
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.source_dir):
                for f in sorted(files):
                    fp = Path(root) / f
                    arcname = fp.relative_to(self.source_dir).as_posix()
                    zf.write(fp, arcname)
        return zip_path


class TestApprovedModelVariants(Stage49TestBase):
    """Verifies that all four approved Gemma 4 variants are individually accepted."""

    APPROVED_VARIANTS = [
        "gemma-4-31b-it-qat-w4a16-ct",
        "gemma-4-12b-it-qat-w4a16-ct",
        "gemma-4-e4b-it-qat-w4a16-ct",
        "gemma-4-e2b-it-qat-w4a16-ct",
    ]

    def test_all_approved_variants_individually_accepted_in_directory(self) -> None:
        """Each currently approved variant must be accepted individually in directory format."""
        for model_id in self.APPROVED_VARIANTS:
            with self.subTest(model=model_id):
                self.write_agent_yaml(
                    f"name: agent_{model_id.replace('-', '_')}\n"
                    f"model: {model_id}\n"
                    f"instruction: !include prompts/root.md\n"
                    f"tools: [read_file, edit_file]\n"
                )
                res = PackageValidator(self.source_dir).validate()
                self.assertTrue(
                    res.overall_valid,
                    f"Approved variant '{model_id}' failed: {[c.diagnostic for c in res.get_failures()]}",
                )
                self.assertIn(model_id, res.discovered_models)
                self.assertEqual(len(res.discovered_models), 1)

                # MODEL_PERMITTED_ALIAS must PASS
                alias_checks = [c for c in res.checks if c.check_id == "MODEL_PERMITTED_ALIAS"]
                self.assertTrue(any(c.status == CheckStatus.PASS for c in alias_checks))

                # MODEL_SINGLE_BASE must PASS
                single_checks = [c for c in res.checks if c.check_id == "MODEL_SINGLE_BASE"]
                self.assertTrue(any(c.status == CheckStatus.PASS for c in single_checks))

    def test_all_approved_variants_individually_accepted_in_zip(self) -> None:
        """Each currently approved variant must be accepted in a packaged ZIP archive."""
        for model_id in self.APPROVED_VARIANTS:
            with self.subTest(model=model_id):
                self.write_agent_yaml(
                    f"name: agent_zip_{model_id.replace('-', '_')}\n"
                    f"model: {model_id}\n"
                    f"instruction: !include prompts/root.md\n"
                    f"tools: [read_file, run_command]\n"
                )
                zip_path = self.make_zip_from_source(f"{model_id}.zip")
                res = PackageValidator(zip_path).validate()
                self.assertTrue(
                    res.overall_valid,
                    f"ZIP validation for '{model_id}' failed: {[c.diagnostic for c in res.get_failures()]}",
                )
                self.assertEqual(res.discovered_models, [model_id])

    def test_root_and_subagent_same_approved_variant_accepted(self) -> None:
        """A package using the same approved variant across root and sub-agents is accepted."""
        (self.source_dir / "prompts" / "sub.md").write_text("# Sub Agent\n", encoding="utf-8")

        for model_id in self.APPROVED_VARIANTS:
            with self.subTest(model=model_id):
                # Write sub-agent with matching model
                self.write_agent_yaml(
                    f"name: sub_agent_{model_id.replace('-', '_')}\n"
                    f"model: {model_id}\n"
                    f"instruction: !include ../prompts/sub.md\n"
                    f"tools: [read_file]\n",
                    rel_path="sub_agents/worker.yaml",
                )
                # Write root agent referencing sub-agent
                self.write_agent_yaml(
                    f"name: root_{model_id.replace('-', '_')}\n"
                    f"model: {model_id}\n"
                    f"instruction: !include prompts/root.md\n"
                    f"sub_agents:\n"
                    f"  - config_path: sub_agents/worker.yaml\n"
                    f"tools: [run_command]\n"
                )

                res = PackageValidator(self.source_dir).validate()
                self.assertTrue(
                    res.overall_valid,
                    f"Homogeneous '{model_id}' failed: {[c.diagnostic for c in res.get_failures()]}",
                )
                self.assertEqual(res.discovered_models, [model_id])
                single_check = next((c for c in res.checks if c.check_id == "MODEL_SINGLE_BASE"), None)
                self.assertIsNotNone(single_check)
                self.assertEqual(single_check.status, CheckStatus.PASS)


class TestMixedAndProhibitedModelVariants(Stage49TestBase):
    """Verifies that mixing models or declaring unapproved/misspelled variants is rejected."""

    def setUp(self) -> None:
        super().setUp()
        (self.source_dir / "prompts" / "sub.md").write_text("# Sub\n", encoding="utf-8")

    def test_mixed_approved_variants_rejected_in_directory(self) -> None:
        """A package mixing two otherwise valid variants (e.g. 31b root and 12b subagent) is rejected."""
        # Root uses 31b
        self.write_agent_yaml(
            f"name: root_mixed\n"
            f"model: gemma-4-31b-it-qat-w4a16-ct\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents:\n"
            f"  - config_path: sub_agents/scout.yaml\n"
            f"tools: [run_command]\n"
        )
        # Sub-agent uses 12b
        self.write_agent_yaml(
            f"name: sub_scout_mixed\n"
            f"model: gemma-4-12b-it-qat-w4a16-ct\n"
            f"instruction: !include ../prompts/sub.md\n"
            f"tools: [read_file]\n",
            rel_path="sub_agents/scout.yaml",
        )

        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid, "Mixed approved models should fail single-base-model rule.")
        self.assertEqual(
            sorted(res.discovered_models),
            ["gemma-4-12b-it-qat-w4a16-ct", "gemma-4-31b-it-qat-w4a16-ct"],
        )
        failures = res.get_failures()
        self.assertTrue(any(f.check_id == "MODEL_SINGLE_BASE" for f in failures))

    def test_mixed_approved_variants_rejected_in_zip(self) -> None:
        """ZIP validation enforces the same rejection on mixed approved models."""
        self.write_agent_yaml(
            f"name: root_mixed_zip\n"
            f"model: gemma-4-e4b-it-qat-w4a16-ct\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents:\n"
            f"  - config_path: sub_agents/worker.yaml\n"
            f"tools: [run_command]\n"
        )
        self.write_agent_yaml(
            f"name: sub_worker_mixed_zip\n"
            f"model: gemma-4-e2b-it-qat-w4a16-ct\n"
            f"instruction: !include ../prompts/sub.md\n"
            f"tools: [read_file]\n",
            rel_path="sub_agents/worker.yaml",
        )
        zip_path = self.make_zip_from_source("mixed.zip")
        res = PackageValidator(zip_path).validate()
        self.assertFalse(res.overall_valid)
        self.assertTrue(any(f.check_id == "MODEL_SINGLE_BASE" for f in res.get_failures()))

    def test_unknown_and_misspelled_variants_rejected(self) -> None:
        """Unknown and misspelled model variants are rejected with MODEL_PERMITTED_ALIAS: FAIL."""
        bad_models = [
            "gemma-4-31b-it-qat",           # Missing quantization/backend suffix
            "gemma-4-31b-it",               # Unquantized alias
            "gemma-4-99b",                  # Non-existent Gemma variant
            "gemma-4-31b-it-w4a16",         # Malformed quantization tag
            "gpt-4",                        # Third-party model
            "claude-3-5-sonnet",            # Third-party model
            "mistral-7b-instruct",          # Third-party model
            "custom-finetune-v1",           # Arbitrary custom name
        ]

        for bad in bad_models:
            with self.subTest(model=bad):
                self.write_agent_yaml(
                    f"name: agent_bad\n"
                    f"model: {bad}\n"
                    f"instruction: !include prompts/root.md\n"
                    f"tools: [read_file]\n"
                )
                res = PackageValidator(self.source_dir).validate()
                self.assertFalse(res.overall_valid, f"Model '{bad}' should be rejected.")
                failures = res.get_failures()
                alias_fail = next((f for f in failures if f.check_id == "MODEL_PERMITTED_ALIAS"), None)
                self.assertIsNotNone(alias_fail, f"Expected MODEL_PERMITTED_ALIAS failure for '{bad}'")
                self.assertEqual(alias_fail.status, CheckStatus.FAIL)
                self.assertEqual(alias_fail.severity, CheckSeverity.FATAL)

    def test_missing_model_on_llm_agent_rejected(self) -> None:
        """Missing or empty model field on LlmAgent is rejected."""
        # 1. Model field omitted entirely
        self.write_agent_yaml(
            "name: agent_no_model\n"
            "instruction: !include prompts/root.md\n"
            "tools: [read_file]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid)
        failures = res.get_failures()
        self.assertTrue(
            any(f.check_id in ("CONFIG_AGENT_MODEL_REQUIRED", "MODEL_DECLARED") for f in failures),
            f"Observed failures: {[f.check_id for f in failures]}",
        )

        # 2. Model field explicitly empty string
        self.write_agent_yaml(
            "name: agent_empty_model\n"
            "model: ''\n"
            "instruction: !include prompts/root.md\n"
            "tools: [read_file]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid)
        failures = res.get_failures()
        self.assertTrue(any(f.check_id == "CONFIG_AGENT_MODEL_REQUIRED" for f in failures))

    def test_provider_prefixes_normalized_correctly(self) -> None:
        """Provider prefixes like google/ or hosted_vllm/ are stripped and accepted."""
        prefixes = [
            ("google/gemma-4-31b-it-qat-w4a16-ct", "gemma-4-31b-it-qat-w4a16-ct"),
            ("hosted_vllm/gemma-4-12b-it-qat-w4a16-ct", "gemma-4-12b-it-qat-w4a16-ct"),
            ("openai/gemma-4-e4b-it-qat-w4a16-ct", "gemma-4-e4b-it-qat-w4a16-ct"),
            ("custom/gemma-4-e2b-it-qat-w4a16-ct", "gemma-4-e2b-it-qat-w4a16-ct"),
            ("'google/gemma-4-31b-it-qat-w4a16-ct'", "gemma-4-31b-it-qat-w4a16-ct"),
            ('"hosted_vllm/gemma-4-31b-it-qat-w4a16-ct"', "gemma-4-31b-it-qat-w4a16-ct"),
        ]

        for raw_model, canonical in prefixes:
            with self.subTest(raw=raw_model):
                self.write_agent_yaml(
                    f"name: agent_prefix\n"
                    f"model: {raw_model}\n"
                    f"instruction: !include prompts/root.md\n"
                    f"tools: [read_file]\n"
                )
                res = PackageValidator(self.source_dir).validate()
                self.assertTrue(
                    res.overall_valid,
                    f"Prefix '{raw_model}' failed: {[c.diagnostic for c in res.get_failures()]}",
                )
                self.assertEqual(res.discovered_models, [canonical])


class TestMalformedSubAgentAndToolConfigs(Stage49TestBase):
    """Verifies that malformed sub_agents and agent_tool configurations are rejected."""

    def test_sub_agents_not_a_list_rejected(self) -> None:
        """sub_agents must be a list; scalar or mapping triggers CONFIG_SUB_AGENTS_LIST: FAIL."""
        self.write_agent_yaml(
            f"name: root_bad_subagents\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents: sub_agents/scout.yaml\n"  # String instead of list
            f"tools: [read_file]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid)
        self.assertTrue(any(f.check_id == "CONFIG_SUB_AGENTS_LIST" for f in res.get_failures()))

    def test_sub_agents_invalid_items_rejected(self) -> None:
        """sub_agents containing integers or dicts without config_path trigger CONFIG_SUB_AGENT_SPEC."""
        # Case A: Integer item
        self.write_agent_yaml(
            f"name: root_bad_item\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents:\n"
            f"  - 12345\n"
            f"tools: [read_file]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid)
        self.assertTrue(any(f.check_id == "CONFIG_SUB_AGENT_SPEC" for f in res.get_failures()))

        # Case B: Dict missing config_path
        self.write_agent_yaml(
            f"name: root_bad_item_dict\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents:\n"
            f"  - name: orphan_subagent\n"
            f"tools: [read_file]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid)
        self.assertTrue(any(f.check_id == "CONFIG_SUB_AGENT_SPEC" for f in res.get_failures()))

        # Case C: Empty string config path
        self.write_agent_yaml(
            f"name: root_bad_empty_path\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents:\n"
            f"  - config_path: ''\n"
            f"tools: [read_file]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid)
        self.assertTrue(any(f.check_id == "CONFIG_SUB_AGENT_SPEC" for f in res.get_failures()))

    def test_agent_tool_malformed_spec_rejected(self) -> None:
        """Malformed agent_tool in tools triggers CONFIG_AGENT_TOOL_SPEC: FAIL."""
        # Case A: agent_tool is integer
        self.write_agent_yaml(
            f"name: root_bad_tool\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"tools:\n"
            f"  - read_file\n"
            f"  - agent_tool: 9999\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid)
        self.assertTrue(any(f.check_id == "CONFIG_AGENT_TOOL_SPEC" for f in res.get_failures()))

        # Case B: agent_tool dict missing config_path
        self.write_agent_yaml(
            f"name: root_bad_tool_dict\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"tools:\n"
            f"  - agent_tool:\n"
            f"      skip_summarization: true\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertFalse(res.overall_valid)
        self.assertTrue(any(f.check_id == "CONFIG_AGENT_TOOL_SPEC" for f in res.get_failures()))

    def test_both_string_and_dict_subagent_specs_accepted(self) -> None:
        """Both string path and mapping with config_path are valid for sub_agents."""
        (self.source_dir / "prompts" / "sub.md").write_text("# Sub\n", encoding="utf-8")
        self.write_agent_yaml(
            f"name: sub_str\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include ../prompts/sub.md\n"
            f"tools: [read_file]\n",
            rel_path="sub_agents/str_sub.yaml",
        )
        self.write_agent_yaml(
            f"name: sub_dict\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include ../prompts/sub.md\n"
            f"tools: [read_file]\n",
            rel_path="sub_agents/dict_sub.yaml",
        )

        self.write_agent_yaml(
            f"name: root_multi_spec\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents:\n"
            f"  - sub_agents/str_sub.yaml\n"
            f"  - config_path: sub_agents/dict_sub.yaml\n"
            f"tools: [run_command]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        self.assertTrue(res.overall_valid, f"Failures: {[c.diagnostic for c in res.get_failures()]}")
        self.assertEqual(res.discovered_models, [PRIMARY_BASE_MODEL])


class TestDirectoryAndZipEquivalence(Stage49TestBase):
    """Verifies that directory and ZIP inspection produce consistent verdicts."""

    def test_parity_on_valid_submission(self) -> None:
        """Directory validation and ZIP validation agree on a valid submission."""
        self.write_agent_yaml(
            f"name: parity_valid\n"
            f"model: gemma-4-12b-it-qat-w4a16-ct\n"
            f"instruction: !include prompts/root.md\n"
            f"tools: [read_file, edit_file]\n"
        )
        zip_path = self.make_zip_from_source("valid_parity.zip")

        res_dir = PackageValidator(self.source_dir).validate()
        res_zip = PackageValidator(zip_path).validate()

        self.assertEqual(res_dir.overall_valid, res_zip.overall_valid)
        self.assertTrue(res_dir.overall_valid)
        self.assertEqual(res_dir.discovered_models, res_zip.discovered_models)
        self.assertEqual(res_dir.failed_count, res_zip.failed_count)
        self.assertEqual(res_dir.failed_count, 0)

    def test_parity_on_invalid_model(self) -> None:
        """Directory validation and ZIP validation agree on rejecting an invalid model."""
        self.write_agent_yaml(
            "name: parity_invalid\n"
            "model: gemma-4-31b-it-qat\n"  # Invalid alias
            "instruction: !include prompts/root.md\n"
            "tools: [read_file]\n"
        )
        zip_path = self.make_zip_from_source("invalid_parity.zip")

        res_dir = PackageValidator(self.source_dir).validate()
        res_zip = PackageValidator(zip_path).validate()

        self.assertEqual(res_dir.overall_valid, res_zip.overall_valid)
        self.assertFalse(res_dir.overall_valid)

        dir_fail_ids = {c.check_id for c in res_dir.get_failures()}
        zip_fail_ids = {c.check_id for c in res_zip.get_failures()}
        self.assertIn("MODEL_PERMITTED_ALIAS", dir_fail_ids)
        self.assertIn("MODEL_PERMITTED_ALIAS", zip_fail_ids)

    def test_parity_on_mixed_models(self) -> None:
        """Directory validation and ZIP validation agree on rejecting mixed models."""
        (self.source_dir / "prompts" / "sub.md").write_text("# Sub\n", encoding="utf-8")
        self.write_agent_yaml(
            f"name: sub_scout\n"
            f"model: gemma-4-e2b-it-qat-w4a16-ct\n"
            f"instruction: !include ../prompts/sub.md\n"
            f"tools: [read_file]\n",
            rel_path="sub_agents/scout.yaml",
        )
        self.write_agent_yaml(
            f"name: root_mixed_parity\n"
            f"model: gemma-4-31b-it-qat-w4a16-ct\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents:\n"
            f"  - config_path: sub_agents/scout.yaml\n"
            f"tools: [run_command]\n"
        )
        zip_path = self.make_zip_from_source("mixed_parity.zip")

        res_dir = PackageValidator(self.source_dir).validate()
        res_zip = PackageValidator(zip_path).validate()

        self.assertEqual(res_dir.overall_valid, res_zip.overall_valid)
        self.assertFalse(res_dir.overall_valid)

        dir_fail_ids = {c.check_id for c in res_dir.get_failures()}
        zip_fail_ids = {c.check_id for c in res_zip.get_failures()}
        self.assertIn("MODEL_SINGLE_BASE", dir_fail_ids)
        self.assertIn("MODEL_SINGLE_BASE", zip_fail_ids)


class TestDiagnosticsAndJsonCompatibility(Stage49TestBase):
    """Verifies --json output schema and stable check identifier compatibility."""

    def test_json_diagnostics_structure(self) -> None:
        """to_json() produces compliant, parseable JSON with all required fields."""
        self.write_agent_yaml(
            f"name: test_agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"tools: [read_file]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        raw_json = res.to_json(indent=2)
        parsed = json.loads(raw_json)

        self.assertIn("target_path", parsed)
        self.assertIn("target_type", parsed)
        self.assertIn("overall_valid", parsed)
        self.assertIn("summary", parsed)
        self.assertIn("checks_executed", parsed["summary"])
        self.assertIn("discovered_models", parsed)
        self.assertIn("checks", parsed)
        self.assertIsInstance(parsed["checks"], list)

        # Each check must have stable attributes
        for chk in parsed["checks"]:
            self.assertIn("check_id", chk)
            self.assertIn("category", chk)
            self.assertIn("status", chk)
            self.assertIn("severity", chk)
            self.assertIn("diagnostic", chk)

    def test_stable_check_identifiers_compatibility(self) -> None:
        """Stable check IDs remain present for downstream harness and CI consumption."""
        self.write_agent_yaml(
            f"name: test_stable\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"tools: [read_file]\n"
        )
        res = PackageValidator(self.source_dir).validate()
        check_ids = {c.check_id for c in res.checks}

        # Core stable identifiers for valid package
        expected_stable = {
            "DIR_ROOT_CONFIG",
            "MODEL_PERMITTED_ALIAS",
            "MODEL_SINGLE_BASE",
            "SECRET_SCAN_CLEAN",
            "MUTATION_SAFETY_INVARIANT",
        }
        for exp_id in expected_stable:
            self.assertIn(exp_id, check_ids, f"Stable check '{exp_id}' missing from results.")

        # Test failure check identifiers on syntax error
        (self.source_dir / "agent.yaml").write_text("name: [unclosed", encoding="utf-8")
        res_fail = PackageValidator(self.source_dir).validate()
        fail_check_ids = {c.check_id for c in res_fail.checks}
        self.assertIn("CONFIG_YAML_SYNTAX", fail_check_ids)


class TestIntraHostDeterminismAndAuditFindings(Stage49TestBase):
    """Verifies intra-host packaging determinism and documents cross-platform audit boundary."""

    def test_packager_intra_host_reproducibility(self) -> None:
        """Repeated packaging runs on the same host yield byte-for-byte identical archives."""
        self.write_agent_yaml(
            f"name: agent_repro\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"tools: [read_file, edit_file]\n"
        )

        zip_a = Path(self.temp_dir) / "build_a.zip"
        manifest_a = Path(self.temp_dir) / "manifest_a.json"
        zip_b = Path(self.temp_dir) / "build_b.zip"
        manifest_b = Path(self.temp_dir) / "manifest_b.json"

        cfg_a = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip_a), manifest_path=str(manifest_a))
        cfg_b = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip_b), manifest_path=str(manifest_b))

        res_a = SubmissionPackager(cfg_a).run()
        res_b = SubmissionPackager(cfg_b).run()

        self.assertTrue(res_a.success)
        self.assertTrue(res_b.success)
        self.assertEqual(res_a.archive_sha256, res_b.archive_sha256)
        self.assertEqual(zip_a.read_bytes(), zip_b.read_bytes())

    def test_packager_aborts_on_unapproved_model(self) -> None:
        """The submission packager refuses to build an archive if model is unapproved."""
        self.write_agent_yaml(
            "name: agent_unapproved\n"
            "model: gemma-4-31b-it\n"  # Unquantized, not in competition allowlist
            "instruction: !include prompts/root.md\n"
            "tools: [read_file]\n"
        )
        zip_path = Path(self.temp_dir) / "should_not_exist.zip"
        manifest_path = Path(self.temp_dir) / "manifest.json"
        cfg = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip_path), manifest_path=str(manifest_path))

        res = SubmissionPackager(cfg).run()
        self.assertFalse(res.success)
        self.assertEqual(res.exit_code, 1)  # Source validation failure
        self.assertFalse(zip_path.exists())

    def test_candidate_configs_m0_to_m5_pass_stage49_policy(self) -> None:
        """All active candidates M0-M5 comply with the updated Stage 49 model policy."""
        candidates_dir = Path("experiments/candidates")
        self.assertTrue(candidates_dir.exists())

        for cand_name in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cand_path = candidates_dir / cand_name
            with self.subTest(candidate=cand_name):
                res = PackageValidator(cand_path).validate()
                self.assertTrue(
                    res.overall_valid,
                    f"Candidate {cand_name} failed Stage 49 validation: {[c.diagnostic for c in res.get_failures()]}",
                )
                self.assertEqual(res.discovered_models, ["gemma-4-31b-it-qat-w4a16-ct"])
                self.assertEqual(res.failed_count, 0)

    def test_sample_submission_passes_stage49_policy(self) -> None:
        """The official sample submission complies with the updated Stage 49 model policy."""
        sample_path = Path("data/competition/sample_submission")
        self.assertTrue(sample_path.exists())

        res = PackageValidator(sample_path).validate()
        self.assertTrue(
            res.overall_valid,
            f"Sample submission failed Stage 49 validation: {[c.diagnostic for c in res.get_failures()]}",
        )
        self.assertEqual(res.discovered_models, ["gemma-4-31b-it-qat-w4a16-ct"])
        self.assertEqual(res.failed_count, 0)

    def test_packaging_and_validating_candidates_m0_to_m5_as_zips(self) -> None:
        """Each candidate M0-M5 can be deterministically packaged into a ZIP and validated cleanly."""
        candidates_dir = Path("experiments/candidates")
        for cand_name in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cand_path = candidates_dir / cand_name
            with self.subTest(candidate=cand_name):
                zip_path = Path(self.temp_dir) / f"{cand_name}.zip"
                manifest_path = Path(self.temp_dir) / f"{cand_name}_manifest.json"
                cfg = PackagerConfig(
                    source_path=str(cand_path),
                    output_path=str(zip_path),
                    manifest_path=str(manifest_path),
                )
                pkg_res = SubmissionPackager(cfg).run()
                self.assertTrue(pkg_res.success, f"Packaging {cand_name} failed: {pkg_res.errors}")
                self.assertTrue(zip_path.exists())

                val_res = PackageValidator(zip_path).validate()
                self.assertTrue(
                    val_res.overall_valid,
                    f"ZIP validation for {cand_name} failed: {[c.diagnostic for c in val_res.get_failures()]}",
                )
                self.assertEqual(val_res.discovered_models, ["gemma-4-31b-it-qat-w4a16-ct"])
                self.assertEqual(val_res.failed_count, 0)


if __name__ == "__main__":
    unittest.main()
