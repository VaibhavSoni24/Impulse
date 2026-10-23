"""Comprehensive unit and adversarial test suite for Stage 47: Package Validator.

Tests:
1. Basic Structure (valid minimal archive, missing agent.yaml, nested agent.yaml, malformed zip, corrupted member)
2. Path Attacks (../ traversal, absolute path, Windows drive, UNC path, symlink, duplicate member, collisions)
3. Configuration Schema (malformed YAML, invalid root mapping, model constraints, prohibited fields, limits)
4. Skills Validation (SKILL.md existence, frontmatter schema, syntax checking, skill size limits)
5. Adapter Validation (valid PEFT, dangling reference, missing files, rank limits, safetensors headers, pickle rejection)
6. Security & Hygiene (secret detection & redaction, .env files, dev artifacts, bomb detection, machine paths)
7. Compatibility & Invariance (M0-M5 directory compatibility, read-only invariance, compiler status reporting, no execution)
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import warnings
import zipfile

# Suppress expected duplicate member warning from zipfile library in adversarial test
warnings.filterwarnings("ignore", category=UserWarning, module="zipfile")

from local.packaging.adapter_validator import validate_safetensors_header
from local.packaging.archive_security import inspect_archive_security
from local.packaging.constants import (
    ALLOWED_MODELS,
    MAX_FILE_COUNT,
    MAX_LORA_RANK,
    MAX_SKILL_SIZE_BYTES,
    MAX_TOTAL_SIZE_BYTES,
    PRIMARY_BASE_MODEL,
)
from local.packaging.models import (
    CheckCategory,
    CheckSeverity,
    CheckStatus,
    PackageValidationResult,
    ValidatorConfig,
)
from local.packaging.reader import ArchivePackageReader, DirectoryPackageReader
from local.packaging.validator import PackageValidator
from scripts.validate_submission import (
    SubmissionValidator,
    normalize_model_name,
    parse_simple_yaml,
    validate_submission_target,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_minimal_safetensors() -> bytes:
    """Creates a valid minimal safetensors binary buffer."""
    hdr = json.dumps({"weight": {"dtype": "BF16", "shape": [16, 16], "data_offsets": [0, 512]}}).encode("utf-8")
    length = len(hdr)
    return struct.pack("<Q", length) + hdr + b"\x00" * 512


def create_test_zip(member_dict: dict[str, bytes | str]) -> bytes:
    """Helper creating an in-memory ZIP archive from a dict of relative paths to contents."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in member_dict.items():
            if isinstance(content, str):
                zf.writestr(name, content.encode("utf-8"))
            else:
                zf.writestr(name, content)
    return buf.getvalue()


class TestBasicStructure(unittest.TestCase):
    """Tests basic archive existence, canonical entrypoint, and corruption detection."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_minimal_archive(self):
        """Valid minimal archive with root agent.yaml passes all checks."""
        agent_yaml = (
            "name: minimal_agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: Execute issue resolution safely.\n"
            "tools:\n"
            "  - run_command\n"
            "  - submit_patch\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "submission.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertTrue(res.overall_valid)
        self.assertEqual(res.failed_count, 0)
        self.assertIsNotNone(res.archive_metadata)
        self.assertEqual(res.archive_metadata.root_config_path, "agent.yaml")

    def test_missing_agent_yaml(self):
        """Archive without agent.yaml fails with MissingRootConfigError."""
        zip_bytes = create_test_zip({"other_config.yaml": "name: test\n"})
        zip_path = Path(self.temp_dir) / "submission.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any("MissingRootConfigError" in c.diagnostic for c in res.get_failures()))

    def test_nested_agent_yaml(self):
        """agent.yaml nested under a subdirectory is rejected."""
        agent_yaml = f"name: agent\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: test\ntools: [run_command]\n"
        zip_bytes = create_test_zip({"submission/agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "submission.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any("nested under subdirectory" in c.diagnostic for c in res.get_failures()))

    def test_multiple_root_configs(self):
        """Multiple root configs (agent.yaml and agent.yml) triggers MultipleRootConfigsError."""
        content = f"name: test\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        zip_bytes = create_test_zip({"agent.yaml": content, "agent.yml": content})
        zip_path = Path(self.temp_dir) / "submission.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any("MultipleRootConfigsError" in c.diagnostic for c in res.get_failures()))

    def test_malformed_zip_file(self):
        """Non-ZIP file fails ARCH_VALID_ZIP check."""
        bad_path = Path(self.temp_dir) / "bad.zip"
        bad_path.write_bytes(b"This is completely invalid zip data\n")

        validator = PackageValidator(bad_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_VALID_ZIP" and c.status == CheckStatus.FAIL for c in res.checks))

    def test_corrupted_member_crc(self):
        """Corrupted member data with invalid CRC is detected."""
        zip_bytes = create_test_zip({"agent.yaml": "test", "file.txt": "hello world"})
        corrupt_bytes = bytearray(zip_bytes)
        corrupt_bytes[40:50] = b"\xFF" * 10
        corrupt_path = Path(self.temp_dir) / "corrupt.zip"
        corrupt_path.write_bytes(bytes(corrupt_bytes))

        checks, _ = inspect_archive_security(corrupt_path)
        self.assertTrue(any(c.status == CheckStatus.FAIL for c in checks))

    def test_missing_referenced_prompt(self):
        """Included prompt that does not exist fails validation."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: !include prompts/missing.md\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "submission.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "INCLUDE_NOT_FOUND" for c in res.get_failures()))

    def test_missing_subagent_config(self):
        """Sub-agent reference whose config_path is missing is caught."""
        agent_yaml = (
            "name: root\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "sub_agents:\n"
            "  - config_path: sub_agents/nonexistent.yaml\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "sub_missing.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "CONFIG_EXISTS" for c in res.get_failures()))


class TestPathAttacks(unittest.TestCase):
    """Tests archive path traversal, symlinks, absolute paths, and collisions."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dot_dot_traversal(self):
        """Member name with ../ traversal is rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("agent.yaml", f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n")
            zf.writestr("../escaped.txt", "escaped content")
        zip_path = Path(self.temp_dir) / "traversal.zip"
        zip_path.write_bytes(buf.getvalue())

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_TRAVERSAL" for c in res.get_failures()))

    def test_absolute_posix_path(self):
        """Member starting with root slash is rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("agent.yaml", f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n")
            zf.writestr("/etc/passwd", "root:x:0:0:")
        zip_path = Path(self.temp_dir) / "abs.zip"
        zip_path.write_bytes(buf.getvalue())

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_ABSOLUTE_PATH" for c in res.get_failures()))

    def test_windows_drive_path(self):
        """Member starting with Windows drive letter is rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("agent.yaml", f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n")
            zf.writestr("C:/Windows/System32/evil.dll", "evil")
        zip_path = Path(self.temp_dir) / "drive.zip"
        zip_path.write_bytes(buf.getvalue())

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_DRIVE_PATH" for c in res.get_failures()))

    def test_unc_path(self):
        """Member starting with UNC share is rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("agent.yaml", f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n")
            zf.writestr("//server/share/evil.txt", "evil")
        zip_path = Path(self.temp_dir) / "unc.zip"
        zip_path.write_bytes(buf.getvalue())

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_UNC_PATH" for c in res.get_failures()))

    def test_symlink_member_rejection(self):
        """Symlink member (S_IFLNK mode in external_attr) is detected and rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("agent.yaml", f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n")
            info = zipfile.ZipInfo("link_to_root")
            info.external_attr = 0o120777 << 16  # S_IFLNK
            zf.writestr(info, "/etc/passwd")
        zip_path = Path(self.temp_dir) / "symlink.zip"
        zip_path.write_bytes(buf.getvalue())

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_SYMLINKS" for c in res.get_failures()))

    def test_duplicate_member_names(self):
        """Duplicate member names in central directory are rejected."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("agent.yaml", f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n")
                zf.writestr("agent.yaml", f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n")
        zip_path = Path(self.temp_dir) / "dup.zip"
        zip_path.write_bytes(buf.getvalue())

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_DUPLICATE_MEMBERS" for c in res.get_failures()))

    def test_case_insensitive_path_collision(self):
        """Files differing only by case trigger case-collision failure."""
        content = f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        zip_bytes = create_test_zip({
            "agent.yaml": content,
            "prompts/root.md": "content 1",
            "prompts/Root.md": "content 2",
        })
        zip_path = Path(self.temp_dir) / "case.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_CASE_COLLISION" for c in res.get_failures()))

    def test_file_directory_collision(self):
        """A path that is both a file and directory prefix is rejected."""
        content = f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        zip_bytes = create_test_zip({
            "agent.yaml": content,
            "prompts": "file content",
            "prompts/system.md": "nested content",
        })
        zip_path = Path(self.temp_dir) / "collision.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_FILE_DIR_COLLISION" for c in res.get_failures()))

    def test_encrypted_member_detection(self):
        """Archive member with encryption bit set is rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("agent.yaml", f"name: x\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n")
            zf.writestr("secret.txt", "encrypted_data")
        raw = bytearray(buf.getvalue())
        cd_header_idx = raw.rfind(b"PK\x01\x02")
        self.assertGreater(cd_header_idx, 0)
        raw[cd_header_idx + 8] |= 0x01  # Set bit 0 (encryption) in central directory header
        zip_path = Path(self.temp_dir) / "encrypted.zip"
        zip_path.write_bytes(bytes(raw))

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ARCH_NO_ENCRYPTION" for c in res.get_failures()))

    def test_include_cycle_detection(self):
        """Recursive include cycles are caught and rejected."""
        agent_yaml = (
            "name: loop\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: !include inc1.yaml\n"
            "tools: [run_command]\n"
        )
        inc1 = "!include inc2.yaml\n"
        inc2 = "!include inc1.yaml\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "inc1.yaml": inc1,
            "inc2.yaml": inc2,
        })
        zip_path = Path(self.temp_dir) / "cycle.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "INCLUDE_CYCLE" for c in res.get_failures()))

    def test_include_escape_root(self):
        """!include path that attempts to escape the root directory is blocked."""
        agent_yaml = (
            "name: escape\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: !include ../../secret.txt\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "escape.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "INCLUDE_PATH_TRAVERSAL" for c in res.get_failures()))


class TestConfigurationSchema(unittest.TestCase):
    """Tests agent schema, model restrictions, prohibited fields, and sub-agents."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_invalid_yaml_syntax(self):
        """Malformed YAML syntax is caught."""
        bad_yaml = "name: [unclosed list\nmodel: gemma-4"
        zip_bytes = create_test_zip({"agent.yaml": bad_yaml})
        zip_path = Path(self.temp_dir) / "syntax.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)

    def test_root_not_mapping(self):
        """YAML whose root is a list or scalar instead of a mapping fails."""
        bad_yaml = "- item 1\n- item 2\n"
        zip_bytes = create_test_zip({"agent.yaml": bad_yaml})
        zip_path = Path(self.temp_dir) / "list_root.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "CONFIG_SCHEMA_MAPPING" for c in res.get_failures()))

    def test_multiple_models_violation(self):
        """Declaring different models between root and sub-agent violates Single Base Model Rule."""
        root_yaml = (
            "name: root\n"
            "model: gemma-4-31b-it-qat-w4a16-ct\n"
            "instruction: Root instructions\n"
            "sub_agents:\n"
            "  - config_path: sub_agents/helper.yaml\n"
            "tools: [run_command]\n"
        )
        sub_yaml = (
            "name: helper\n"
            "model: gemma-4-9b-it\n"
            "instruction: Helper instructions\n"
            "tools: [read_file]\n"
        )
        zip_bytes = create_test_zip({
            "agent.yaml": root_yaml,
            "sub_agents/helper.yaml": sub_yaml,
        })
        zip_path = Path(self.temp_dir) / "multi_model.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "MODEL_SINGLE_BASE" and c.status == CheckStatus.FAIL for c in res.get_failures()))

    def test_prohibited_generate_content_config_fields(self):
        """Prohibited fields inside generate_content_config are rejected."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
            "generate_content_config:\n"
            "  tools: [forbidden_tool]\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "prohibited.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "CONFIG_PROHIBITED_FIELD" for c in res.get_failures()))

    def test_max_output_tokens_exceeded(self):
        """max_output_tokens > 32768 is rejected."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
            "generate_content_config:\n"
            "  max_output_tokens: 65536\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "tokens.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "CONFIG_MAX_OUTPUT_TOKENS" for c in res.get_failures()))

    def test_thinking_budget_exceeded(self):
        """thinking_budget > 32768 is rejected."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
            "generate_content_config:\n"
            "  thinking_config:\n"
            "    thinking_budget: 99999\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "thinking.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "CONFIG_THINKING_BUDGET" for c in res.get_failures()))

    def test_invalid_thinking_level(self):
        """Invalid thinking_level string is rejected."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
            "generate_content_config:\n"
            "  thinking_config:\n"
            "    thinking_level: ultra_extreme\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "level.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "CONFIG_THINKING_LEVEL" for c in res.get_failures()))


class TestSkillsValidation(unittest.TestCase):
    """Tests skill manifest, frontmatter, directory limits, and script syntax."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_skill(self):
        """Skill with valid frontmatter and clean python script passes."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "skills:\n"
            "  - skills/test_skill\n"
            "tools: [run_command]\n"
        )
        skill_md = "---\nname: test_skill\ndescription: A test skill\n---\n# Guide\n"
        skill_py = "def helper():\n    return 42\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "skills/test_skill/SKILL.md": skill_md,
            "skills/test_skill/helper.py": skill_py,
        })
        zip_path = Path(self.temp_dir) / "skill.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertTrue(res.overall_valid)
        self.assertTrue(any(c.check_id == "SKILL_MANIFEST_NAME" and c.status == CheckStatus.PASS for c in res.checks))
        self.assertTrue(any(c.check_id == "SKILL_SCRIPT_SYNTAX" and c.status == CheckStatus.PASS for c in res.checks))

    def test_missing_skill_md(self):
        """Skill directory without SKILL.md fails validation."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "skills:\n"
            "  - skills/broken_skill\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "skills/broken_skill/notes.txt": "missing manifest",
        })
        zip_path = Path(self.temp_dir) / "broken_skill.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "SKILL_MD_EXISTS" and c.status == CheckStatus.FAIL for c in res.get_failures()))

    def test_missing_name_in_frontmatter(self):
        """SKILL.md frontmatter missing required 'name' field fails."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "skills:\n"
            "  - skills/no_name_skill\n"
            "tools: [run_command]\n"
        )
        skill_md = "---\ndescription: Skill without name field\n---\n# Content\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "skills/no_name_skill/SKILL.md": skill_md,
        })
        zip_path = Path(self.temp_dir) / "no_name.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "SKILL_MANIFEST_NAME" and c.status == CheckStatus.FAIL for c in res.get_failures()))

    def test_invalid_yaml_frontmatter(self):
        """SKILL.md with unparseable frontmatter fails."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "skills:\n"
            "  - skills/bad_fm\n"
            "tools: [run_command]\n"
        )
        skill_md = "---\nname: [unclosed\n---\n# Content\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "skills/bad_fm/SKILL.md": skill_md,
        })
        zip_path = Path(self.temp_dir) / "bad_fm.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "SKILL_FRONTMATTER_PARSE" and c.status == CheckStatus.FAIL for c in res.get_failures()))

    def test_skill_script_syntax_error(self):
        """Python script with SyntaxError inside a skill is caught statically without execution."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: instructions\n"
            "skills:\n"
            "  - skills/syntax_err_skill\n"
            "tools: [run_command]\n"
        )
        skill_md = "---\nname: syntax_err_skill\n---\n# Body\n"
        bad_py = "def bad_func(:\n    pass\n"  # SyntaxError
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "skills/syntax_err_skill/SKILL.md": skill_md,
            "skills/syntax_err_skill/bad.py": bad_py,
        })
        zip_path = Path(self.temp_dir) / "bad_script.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "SKILL_SCRIPT_SYNTAX" and c.status == CheckStatus.FAIL for c in res.get_failures()))


class TestAdapterValidation(unittest.TestCase):
    """Tests PEFT LoRA adapter directory, config schema, safetensors headers, and weight constraints."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_adapter(self):
        """Valid PEFT LoRA adapter passes validation."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "adapter: my_lora\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
        )
        adapter_cfg = json.dumps({
            "base_model_name_or_path": PRIMARY_BASE_MODEL,
            "peft_type": "LORA",
            "r": 16,
            "target_modules": ["q_proj", "v_proj"],
        })
        safetensors_bytes = make_minimal_safetensors()
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "adapters/my_lora/adapter_config.json": adapter_cfg,
            "adapters/my_lora/adapter_model.safetensors": safetensors_bytes,
        })
        zip_path = Path(self.temp_dir) / "adapter.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertTrue(res.overall_valid)
        self.assertTrue(any(c.check_id == "ADAPTER_PEFT_TYPE" and c.status == CheckStatus.PASS for c in res.checks))
        self.assertTrue(any(c.check_id == "ADAPTER_SAFETENSORS_HEADER" and c.status == CheckStatus.PASS for c in res.checks))

    def test_dangling_adapter_reference(self):
        """Adapter declared in agent.yaml that does not exist in package fails."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "adapter: missing_lora\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "dangling.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any("DanglingAdapterReferenceError" in c.diagnostic for c in res.get_failures()))

    def test_missing_adapter_config(self):
        """Adapter directory missing adapter_config.json fails."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "adapter: no_cfg\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "adapters/no_cfg/adapter_model.safetensors": make_minimal_safetensors(),
        })
        zip_path = Path(self.temp_dir) / "no_cfg.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ADAPTER_CONFIG_EXISTS" for c in res.get_failures()))

    def test_missing_adapter_weights(self):
        """Adapter directory missing adapter_model.safetensors fails."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "adapter: no_weights\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
        )
        adapter_cfg = json.dumps({
            "base_model_name_or_path": PRIMARY_BASE_MODEL,
            "peft_type": "LORA",
            "r": 8,
            "target_modules": ["q_proj"],
        })
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "adapters/no_weights/adapter_config.json": adapter_cfg,
        })
        zip_path = Path(self.temp_dir) / "no_weights.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ADAPTER_WEIGHTS_EXISTS" for c in res.get_failures()))

    def test_malformed_adapter_json(self):
        """Malformed JSON inside adapter_config.json fails."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "adapter: bad_json_lora\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "adapters/bad_json_lora/adapter_config.json": "{bad_json: missing_quotes}",
            "adapters/bad_json_lora/adapter_model.safetensors": make_minimal_safetensors(),
        })
        zip_path = Path(self.temp_dir) / "bad_json.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ADAPTER_CONFIG_PARSE" for c in res.get_failures()))

    def test_prohibited_pickle_weights(self):
        """Pickle-based weight (.bin / .pt) inside adapter is rejected."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "adapter: pickle_lora\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
        )
        adapter_cfg = json.dumps({
            "base_model_name_or_path": PRIMARY_BASE_MODEL,
            "peft_type": "LORA",
            "r": 8,
            "target_modules": ["q_proj"],
        })
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "adapters/pickle_lora/adapter_config.json": adapter_cfg,
            "adapters/pickle_lora/adapter_model.safetensors": make_minimal_safetensors(),
            "adapters/pickle_lora/adapter_model.bin": b"pickle_bytes",
        })
        zip_path = Path(self.temp_dir) / "pickle.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ADAPTER_PROHIBITED_WEIGHTS" for c in res.get_failures()))

    def test_corrupt_safetensors_header(self):
        """Safetensors file with corrupt header fails validation."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "adapter: corrupt_hdr_lora\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
        )
        adapter_cfg = json.dumps({
            "base_model_name_or_path": PRIMARY_BASE_MODEL,
            "peft_type": "LORA",
            "r": 8,
            "target_modules": ["q_proj"],
        })
        # Invalid header length (0)
        corrupt_weights = struct.pack("<Q", 0) + b"junk"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "adapters/corrupt_hdr_lora/adapter_config.json": adapter_cfg,
            "adapters/corrupt_hdr_lora/adapter_model.safetensors": corrupt_weights,
        })
        zip_path = Path(self.temp_dir) / "corrupt_hdr.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ADAPTER_SAFETENSORS_HEADER" and c.status == CheckStatus.FAIL for c in res.get_failures()))

    def test_rank_exceeds_max(self):
        """Adapter rank r=256 exceeding MAX_LORA_RANK (128) is rejected."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "adapter: big_rank_lora\n"
            "instruction: instructions\n"
            "tools: [run_command]\n"
        )
        adapter_cfg = json.dumps({
            "base_model_name_or_path": PRIMARY_BASE_MODEL,
            "peft_type": "LORA",
            "r": 256,
            "target_modules": ["q_proj"],
        })
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "adapters/big_rank_lora/adapter_config.json": adapter_cfg,
            "adapters/big_rank_lora/adapter_model.safetensors": make_minimal_safetensors(),
        })
        zip_path = Path(self.temp_dir) / "big_rank.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "ADAPTER_RANK_BOUNDS" for c in res.get_failures()))


class TestSecurityAndHygiene(unittest.TestCase):
    """Tests secret scanning, .env detection, dev artifacts, and host path warnings."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fake_api_key_redacted_diagnostic(self):
        """Fake API key is detected, flagged, and REDACTED in diagnostics."""
        fake_token = "ghp_1234567890abcdef1234567890abcdef"
        prompt_with_secret = f"Use this token for auth: {fake_token}\n"
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: !include prompts/system.md\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "prompts/system.md": prompt_with_secret,
        })
        zip_path = Path(self.temp_dir) / "secret.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        failures = res.get_failures()
        secret_failures = [c for c in failures if c.check_id == "SECRET_DETECTED"]
        self.assertTrue(len(secret_failures) > 0)
        # CRITICAL: Confirm full secret token is NOT leaked in diagnostic output
        self.assertNotIn(fake_token, secret_failures[0].diagnostic)
        self.assertIn("***REDACTED***", secret_failures[0].diagnostic)

    def test_fake_private_key_redacted(self):
        """Fake RSA private key is detected and masked in diagnostics."""
        fake_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
        agent_yaml = f"name: agent\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "prompts/key.txt": fake_key,
        })
        zip_path = Path(self.temp_dir) / "privkey.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        failures = [c for c in res.get_failures() if c.check_id == "SECRET_DETECTED"]
        self.assertTrue(len(failures) > 0)
        self.assertIn("***REDACTED***", failures[0].diagnostic)

    def test_env_file_detected(self):
        """Prohibited .env file is caught and rejected."""
        agent_yaml = f"name: agent\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            ".env": "SECRET_KEY=supersecret123\n",
        })
        zip_path = Path(self.temp_dir) / "env.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "HYGIENE_NO_ENV_FILES" for c in res.get_failures()))

    def test_development_directory_detected(self):
        """Development directory (.git) inside archive is rejected."""
        agent_yaml = f"name: agent\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            ".git/config": "[core]\nrepositoryformatversion = 0\n",
        })
        zip_path = Path(self.temp_dir) / "dev_dir.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "HYGIENE_NO_DEV_DIRS" for c in res.get_failures()))

    def test_prohibited_test_script_at_root(self):
        """Unit test script packaged at package root is rejected."""
        agent_yaml = f"name: agent\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "test_something.py": "def test_foo(): pass\n",
        })
        zip_path = Path(self.temp_dir) / "test_file.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "HYGIENE_NO_TEST_FILES" for c in res.get_failures()))

    def test_prohibited_log_file(self):
        """Temporary or log file is rejected."""
        agent_yaml = f"name: agent\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        zip_bytes = create_test_zip({
            "agent.yaml": agent_yaml,
            "debug.log": "test log",
        })
        zip_path = Path(self.temp_dir) / "log.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertFalse(res.overall_valid)
        self.assertTrue(any(c.check_id == "HYGIENE_NO_TEMP_FILES" for c in res.get_failures()))

    def test_host_machine_path_warning(self):
        """Developer host path generates a WARNING without failing non-strict validation."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: 'Refer to C:\\\\Users\\\\developer\\\\notes.txt'\n"
            "tools: [run_command]\n"
        )
        zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
        zip_path = Path(self.temp_dir) / "hostpath.zip"
        zip_path.write_bytes(zip_bytes)

        validator = PackageValidator(zip_path)
        res = validator.validate()

        self.assertTrue(res.overall_valid)
        self.assertTrue(any(c.check_id == "HYGIENE_HOST_PATH" and c.status == CheckStatus.WARNING for c in res.checks))


class TestCompatibilityAndInvariance(unittest.TestCase):
    """Tests candidate directory compatibility, mutation safety, and compiler reporting."""

    def test_m0_through_m5_compatibility(self):
        """All existing candidates M0..M5 pass validation cleanly via SubmissionValidator."""
        for m in range(6):
            cand_dir = PROJECT_ROOT / f"experiments/candidates/M{m}"
            validator = SubmissionValidator(cand_dir)
            passed = validator.validate()
            self.assertTrue(passed, f"Candidate M{m} failed validation: {validator.errors}")
            self.assertEqual(len(validator.errors), 0)
            self.assertIn("gemma-4-31b-it-qat-w4a16-ct", validator.discovered_models)

    def test_read_only_mutation_safety(self):
        """Validation confirms target package is 100% byte-for-byte immutable."""
        agent_yaml = f"name: safe\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: immutable\ntools: [run_command]\n"
        temp_dir = tempfile.mkdtemp()
        try:
            zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
            zip_path = Path(temp_dir) / "test_immutability.zip"
            zip_path.write_bytes(zip_bytes)

            sha_before = zip_path.read_bytes()

            validator = PackageValidator(zip_path)
            res = validator.validate()

            sha_after = zip_path.read_bytes()

            self.assertEqual(sha_before, sha_after)
            self.assertTrue(any(c.check_id == "MUTATION_SAFETY_INVARIANT" and c.status == CheckStatus.PASS for c in res.checks))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_official_compiler_status_unsupported(self):
        """When official compiler is not installed, reports UNAVAILABLE without failing valid packages."""
        agent_yaml = f"name: agent\nmodel: {PRIMARY_BASE_MODEL}\ninstruction: x\ntools: [run_command]\n"
        temp_dir = tempfile.mkdtemp()
        try:
            zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
            zip_path = Path(temp_dir) / "submission.zip"
            zip_path.write_bytes(zip_bytes)

            validator = PackageValidator(zip_path)
            res = validator.validate()

            self.assertTrue(res.overall_valid)
            compiler_check = [c for c in res.checks if c.check_id == "COMPILER_OFFICIAL_AVAILABILITY"]
            self.assertEqual(len(compiler_check), 1)
            self.assertEqual(compiler_check[0].status, CheckStatus.UNAVAILABLE)
            self.assertIn("adk-submission compile", compiler_check[0].diagnostic)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_script_is_never_executed(self):
        """Validates that skill scripts are never executed during validation."""
        marker_file = PROJECT_ROOT / "temp_execution_marker.tmp"
        if marker_file.exists():
            marker_file.unlink()

        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: x\n"
            "skills: [skills/side_effect]\n"
            "tools: [run_command]\n"
        )
        skill_md = "---\nname: side_effect\n---\n# Guide\n"
        # Script that would write marker file if executed
        malicious_py = f"import pathlib\npathlib.Path('{marker_file.as_posix()}').write_text('executed')\n"

        temp_dir = tempfile.mkdtemp()
        try:
            zip_bytes = create_test_zip({
                "agent.yaml": agent_yaml,
                "skills/side_effect/SKILL.md": skill_md,
                "skills/side_effect/script.py": malicious_py,
            })
            zip_path = Path(temp_dir) / "side_effect.zip"
            zip_path.write_bytes(zip_bytes)

            validator = PackageValidator(zip_path)
            res = validator.validate()

            # Confirm marker file was NEVER created
            self.assertFalse(marker_file.exists(), "SECURITY VIOLATION: Skill script was executed during validation!")
        finally:
            if marker_file.exists():
                marker_file.unlink()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_strict_mode_rejects_warnings(self):
        """In strict mode, warnings cause overall_valid to be False."""
        agent_yaml = (
            "name: agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            "instruction: 'C:\\\\Users\\\\developer\\\\test.txt'\n"  # triggers host path warning
            "tools: [run_command]\n"
        )
        temp_dir = tempfile.mkdtemp()
        try:
            zip_bytes = create_test_zip({"agent.yaml": agent_yaml})
            zip_path = Path(temp_dir) / "warn.zip"
            zip_path.write_bytes(zip_bytes)

            # Normal mode -> overall_valid is True
            normal_val = PackageValidator(zip_path, ValidatorConfig(strict_mode=False))
            normal_res = normal_val.validate()
            self.assertTrue(normal_res.overall_valid)
            self.assertTrue(normal_res.warnings_count > 0)

            # Strict mode -> overall_valid is False
            strict_val = PackageValidator(zip_path, ValidatorConfig(strict_mode=True))
            strict_res = strict_val.validate()
            self.assertFalse(strict_res.overall_valid)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
