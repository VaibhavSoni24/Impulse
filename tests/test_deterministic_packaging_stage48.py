"""Focused test suite for IMPULSE Stage 48: Deterministic Submission Packaging.

Verifies:
- Basic packaging (minimal, sub-agents, skills, adapters, root agent.yaml, normalized paths)
- Determinism (byte-for-byte reproducibility, order invariance, timestamp invariance, exclusion invariance, diff sensitivity)
- Security (symlink rejection, path escape rejection, credential blocking, missing includes, atomic failure, overwrite policy, source immutability)
- CLI and exit codes (help, missing source, invalid source, check-only mode, JSON schema, manifest consistency)
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import zipfile

from local.packaging.constants import PRIMARY_BASE_MODEL
from local.packaging.models import PackagerConfig, PackagerResult, ValidatorConfig

from local.packaging.packager import (
    SubmissionPackager,
    collect_source_files,
    compute_file_sha256,
    verify_manifest_archive_consistency,
)
from local.packaging.validator import PackageValidator
from scripts.package_submission import main as cli_main



class BasePackagingTestCase(unittest.TestCase):
    """Base fixture creating isolated temporary directory hierarchies."""

    def setUp(self):
        self.test_root = tempfile.mkdtemp(prefix="impulse_stage48_")
        self.source_dir = Path(self.test_root) / "source_pkg"
        self.source_dir.mkdir(parents=True)
        self.out_dir = Path(self.test_root) / "output"
        self.out_dir.mkdir(parents=True)
        self.zip_path = self.out_dir / "submission.zip"
        self.manifest_path = self.out_dir / "submission.manifest.json"

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def create_minimal_package(self, pkg_dir: Path | None = None) -> Path:
        target = pkg_dir or self.source_dir
        target.mkdir(parents=True, exist_ok=True)
        (target / "agent.yaml").write_text(
            f"name: test_agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"tools:\n"
            f"  - run_command\n"
            f"  - submit_patch\n"
            f"generate_content_config:\n"
            f"  max_output_tokens: 4096\n",
            encoding="utf-8",
        )
        prompts = target / "prompts"
        prompts.mkdir(parents=True, exist_ok=True)
        (prompts / "root.md").write_text("# Root Prompt Instructions\nFollow test suite.\n", encoding="utf-8")
        return target


class TestBasicPackaging(BasePackagingTestCase):
    """Tests basic packaging workflows for valid agent configurations."""

    def test_minimal_package_creation(self):
        """Creates a valid minimal package with root agent.yaml and included prompt."""
        self.create_minimal_package()

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        packager = SubmissionPackager(cfg)
        res = packager.run()

        self.assertTrue(res.success, f"Packaging failed with errors: {res.errors}")
        self.assertEqual(res.exit_code, 0)
        self.assertTrue(self.zip_path.is_file())
        self.assertTrue(self.manifest_path.is_file())
        self.assertEqual(res.total_files_packaged, 2)

        # Confirm agent.yaml is at archive root
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            names = zf.namelist()
            self.assertIn("agent.yaml", names)
            self.assertIn("prompts/root.md", names)
            self.assertEqual(len(names), 2)

    def test_package_with_multiple_subagents(self):
        """Creates a package containing multiple sub-agents and includes."""
        self.create_minimal_package()

        sub_dir = self.source_dir / "sub_agents"
        sub_dir.mkdir()
        (sub_dir / "scout.yaml").write_text(
            f"name: scout\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include ../prompts/scout.md\n"
            f"tools: [read_file]\n",
            encoding="utf-8",
        )
        (sub_dir / "debugger.yaml").write_text(
            f"name: debugger\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: Debug the issue.\n"
            f"tools: [read_file, edit_file]\n",
            encoding="utf-8",
        )
        (self.source_dir / "prompts" / "scout.md").write_text("# Scout Instructions\n", encoding="utf-8")

        # Update root agent.yaml to declare sub-agents
        (self.source_dir / "agent.yaml").write_text(
            f"name: root_with_specialists\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"sub_agents:\n"
            f"  - sub_agents/scout.yaml\n"
            f"  - sub_agents/debugger.yaml\n"
            f"tools: [run_command]\n",
            encoding="utf-8",
        )

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        res = SubmissionPackager(cfg).run()

        self.assertTrue(res.success, f"Errors: {res.errors}")
        self.assertEqual(res.total_files_packaged, 5)

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            members = sorted(zf.namelist())
            self.assertEqual(
                members,
                [
                    "agent.yaml",
                    "prompts/root.md",
                    "prompts/scout.md",
                    "sub_agents/debugger.yaml",
                    "sub_agents/scout.yaml",
                ],
            )

    def test_package_with_skills(self):
        """Creates a package with an ADK skill directory and SKILL.md manifest."""
        self.create_minimal_package()

        skill_dir = self.source_dir / "skills" / "repo_triage"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: repo_triage\ndescription: Triage repository issues.\n---\n# Skill Guide\n",
            encoding="utf-8",
        )

        (self.source_dir / "agent.yaml").write_text(
            f"name: root_with_skills\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"skills:\n"
            f"  - skills/repo_triage\n"
            f"tools: [run_command]\n",
            encoding="utf-8",
        )

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        res = SubmissionPackager(cfg).run()

        self.assertTrue(res.success, f"Errors: {res.errors}")
        self.assertEqual(res.total_files_packaged, 3)

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            self.assertIn("skills/repo_triage/SKILL.md", zf.namelist())

    def test_package_with_adapters(self):
        """Creates a package with a PEFT LoRA adapter and safetensors weights."""
        self.create_minimal_package()

        adapter_dir = self.source_dir / "adapters" / "lora_weights"
        adapter_dir.mkdir(parents=True)
        (adapter_dir / "adapter_config.json").write_text(
            json.dumps({
                "peft_type": "LORA",
                "r": 16,
                "lora_alpha": 32,
                "target_modules": ["q_proj", "v_proj"],
            }),
            encoding="utf-8",
        )

        # Minimal valid safetensors file: 8-byte uint64 header length + JSON header dict
        header_json = json.dumps({"__metadata__": {"format": "pt"}}).encode("utf-8")
        header_len = len(header_json)
        safetensors_bytes = header_len.to_bytes(8, byteorder="little") + header_json
        (adapter_dir / "adapter_model.safetensors").write_bytes(safetensors_bytes)

        (self.source_dir / "agent.yaml").write_text(
            f"name: root_with_adapter\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/root.md\n"
            f"adapters:\n"
            f"  - adapters/lora_weights\n"
            f"tools: [run_command]\n",
            encoding="utf-8",
        )

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        res = SubmissionPackager(cfg).run()

        self.assertTrue(res.success, f"Errors: {res.errors}")
        self.assertEqual(res.total_files_packaged, 4)

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            self.assertIn("adapters/lora_weights/adapter_config.json", zf.namelist())
            self.assertIn("adapters/lora_weights/adapter_model.safetensors", zf.namelist())


class TestDeterminism(BasePackagingTestCase):
    """Tests byte-for-byte reproducibility across runs and environments."""

    def test_byte_for_byte_identical_rebuilds(self):
        """Two packaging runs from identical inputs produce exact same SHA-256 and bytes."""
        self.create_minimal_package()

        zip1 = self.out_dir / "run1.zip"
        man1 = self.out_dir / "run1.manifest.json"
        zip2 = self.out_dir / "run2.zip"
        man2 = self.out_dir / "run2.manifest.json"

        cfg1 = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip1), manifest_path=str(man1))
        cfg2 = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip2), manifest_path=str(man2))

        res1 = SubmissionPackager(cfg1).run()
        res2 = SubmissionPackager(cfg2).run()

        self.assertTrue(res1.success)
        self.assertTrue(res2.success)

        bytes1 = zip1.read_bytes()
        bytes2 = zip2.read_bytes()

        self.assertEqual(bytes1, bytes2, "Archive byte contents differ across repeated builds.")
        self.assertEqual(res1.archive_sha256, res2.archive_sha256)
        self.assertEqual(compute_file_sha256(zip1), compute_file_sha256(zip2))

    def test_file_enumeration_order_invariance(self):
        """Changing the creation/enumeration order on disk does not change ZIP bytes."""
        self.create_minimal_package()

        # Add multiple files in different subdirectories
        (self.source_dir / "prompts" / "z_last.md").write_text("Z content\n", encoding="utf-8")
        (self.source_dir / "prompts" / "a_first.md").write_text("A content\n", encoding="utf-8")
        (self.source_dir / "prompts" / "m_middle.md").write_text("M content\n", encoding="utf-8")

        zip1 = self.out_dir / "order1.zip"
        man1 = self.out_dir / "order1.manifest.json"
        cfg1 = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip1), manifest_path=str(man1))
        res1 = SubmissionPackager(cfg1).run()
        self.assertTrue(res1.success)

        # In a second directory, create files in reverse chronological order
        source2 = Path(self.test_root) / "source_pkg_reverse"
        source2.mkdir(parents=True)
        (source2 / "prompts").mkdir(parents=True)
        (source2 / "prompts" / "m_middle.md").write_text("M content\n", encoding="utf-8")
        (source2 / "prompts" / "z_last.md").write_text("Z content\n", encoding="utf-8")
        (source2 / "prompts" / "a_first.md").write_text("A content\n", encoding="utf-8")
        (source2 / "prompts" / "root.md").write_text("# Root Prompt Instructions\nFollow test suite.\n", encoding="utf-8")
        (source2 / "agent.yaml").write_text((self.source_dir / "agent.yaml").read_text(encoding="utf-8"), encoding="utf-8")

        zip2 = self.out_dir / "order2.zip"
        man2 = self.out_dir / "order2.manifest.json"
        cfg2 = PackagerConfig(source_path=str(source2), output_path=str(zip2), manifest_path=str(man2))
        res2 = SubmissionPackager(cfg2).run()
        self.assertTrue(res2.success)

        self.assertEqual(zip1.read_bytes(), zip2.read_bytes())
        self.assertEqual(res1.archive_sha256, res2.archive_sha256)

    def test_zip_metadata_stability(self):
        """ZIP entries have fixed timestamp, Unix system, and fixed file mode permissions."""
        self.create_minimal_package()

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        res = SubmissionPackager(cfg).run()
        self.assertTrue(res.success)

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            for info in zf.infolist():
                self.assertEqual(info.date_time, (2026, 1, 1, 0, 0, 0))
                self.assertEqual(info.create_system, 3)  # Unix
                mode = (info.external_attr >> 16) & 0xFFFF
                self.assertEqual(mode, 0o100644)  # S_IFREG | rw-r--r--
                self.assertEqual(info.comment, b"")

    def test_file_modification_changes_hash(self):
        """Modifying one file in the package produces a different member hash and archive hash."""
        self.create_minimal_package()

        zip1 = self.out_dir / "base.zip"
        man1 = self.out_dir / "base.manifest.json"
        cfg1 = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip1), manifest_path=str(man1))
        res1 = SubmissionPackager(cfg1).run()

        # Modify root.md
        (self.source_dir / "prompts" / "root.md").write_text("# Modified Root Prompt\n", encoding="utf-8")

        zip2 = self.out_dir / "modified.zip"
        man2 = self.out_dir / "modified.manifest.json"
        cfg2 = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip2), manifest_path=str(man2))
        res2 = SubmissionPackager(cfg2).run()

        self.assertNotEqual(res1.archive_sha256, res2.archive_sha256)
        self.assertNotEqual(zip1.read_bytes(), zip2.read_bytes())

    def test_excluded_files_do_not_alter_archive(self):
        """Adding or modifying excluded development files (.git, .gitignore, tests, logs) does not alter ZIP."""
        self.create_minimal_package()

        zip1 = self.out_dir / "clean.zip"
        man1 = self.out_dir / "clean.manifest.json"
        cfg1 = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip1), manifest_path=str(man1))
        res1 = SubmissionPackager(cfg1).run()

        # Add development debris to source directory
        (self.source_dir / ".gitignore").write_text("*.pyc\n.env\n", encoding="utf-8")
        (self.source_dir / "test_scratch.py").write_text("import unittest\n", encoding="utf-8")
        (self.source_dir / "execution.log").write_text("2026-10-23 LOG MSG\n", encoding="utf-8")
        pycache = self.source_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "agent.cpython-310.pyc").write_bytes(b"\x00\x01\x02")

        zip2 = self.out_dir / "with_debris.zip"
        man2 = self.out_dir / "with_debris.manifest.json"
        cfg2 = PackagerConfig(source_path=str(self.source_dir), output_path=str(zip2), manifest_path=str(man2))
        res2 = SubmissionPackager(cfg2).run()

        self.assertTrue(res2.success)
        self.assertEqual(res1.archive_sha256, res2.archive_sha256)
        self.assertEqual(zip1.read_bytes(), zip2.read_bytes())
        self.assertGreater(len(res2.excluded_files), 0)


class TestSecurity(BasePackagingTestCase):
    """Tests security controls, symlink rejection, credential scanning, and atomic failure handling."""

    def test_symlink_rejection_without_following(self):
        """Symlinks inside the source directory are rejected immediately."""
        self.create_minimal_package()

        def fake_sym(p):
            return getattr(p, "name", "") == "evil_link"

        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=fake_sym):
            (self.source_dir / "evil_link").write_text("target", encoding="utf-8")

            cfg = PackagerConfig(
                source_path=str(self.source_dir),
                output_path=str(self.zip_path),
                manifest_path=str(self.manifest_path),
            )
            res = SubmissionPackager(cfg).run()

            self.assertFalse(res.success)
            self.assertEqual(res.exit_code, 1)
            self.assertTrue(any("symlink" in e.lower() for e in res.errors))
            self.assertFalse(self.zip_path.exists())


    def test_escaping_path_rejection(self):
        """Relative path escaping source directory is rejected."""
        self.create_minimal_package()

        with mock.patch("local.packaging.packager.os.walk") as mock_walk:
            mock_walk.return_value = [
                (str(self.source_dir), [], ["agent.yaml", "prompts/root.md"]),
                (str(self.source_dir.parent), [], ["../escaped.txt"]),
            ]
            members, excluded, errors = collect_source_files(self.source_dir)
            self.assertTrue(any("escaping" in err.lower() or "unsafe" in err.lower() for err in errors))

    def test_credentials_prevent_packaging(self):
        """Fake API keys in prompt files fail source validation and prevent archive creation."""
        self.create_minimal_package()
        # Embed synthetic fake API key in prompt
        (self.source_dir / "prompts" / "root.md").write_text(
            "Use GitHub token: ghp_111122223333444455556666777788889999\n",
            encoding="utf-8",
        )

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        res = SubmissionPackager(cfg).run()

        self.assertFalse(res.success)
        self.assertEqual(res.exit_code, 1)
        self.assertFalse(self.zip_path.exists())
        self.assertFalse(self.manifest_path.exists())

    def test_missing_include_prevents_packaging(self):
        """Referencing a nonexistent file via !include fails validation and prevents packaging."""
        self.create_minimal_package()
        (self.source_dir / "agent.yaml").write_text(
            f"name: test_agent\n"
            f"model: {PRIMARY_BASE_MODEL}\n"
            f"instruction: !include prompts/nonexistent.md\n"
            f"tools: [run_command]\n",
            encoding="utf-8",
        )

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        res = SubmissionPackager(cfg).run()

        self.assertFalse(res.success)
        self.assertEqual(res.exit_code, 1)
        self.assertFalse(self.zip_path.exists())

    def test_failed_writes_do_not_leave_partial_zip(self):
        """If an error occurs during writing or post-verification, no partial ZIP is left on disk."""
        self.create_minimal_package()

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        packager = SubmissionPackager(cfg)

        # Evaluate base validation before patching
        source_val = PackageValidator(
            self.source_dir,
            ValidatorConfig(ignore_excluded_dev_files=True),
        ).validate()
        bad_archive_val = PackageValidator(
            self.source_dir,
            ValidatorConfig(ignore_excluded_dev_files=True),
        ).validate()
        bad_archive_val.overall_valid = False

        # Mock PackageValidator.validate to succeed for source but fail for generated archive
        with mock.patch("local.packaging.packager.PackageValidator.validate") as mock_val:
            mock_val.side_effect = [source_val, bad_archive_val]

            res = packager.run()

            self.assertFalse(res.success)
            self.assertEqual(res.exit_code, 2)
            self.assertFalse(self.zip_path.exists(), "Partial ZIP was not cleaned up!")
            self.assertFalse(self.manifest_path.exists())


    def test_overwrite_protection_without_force(self):
        """Pre-existing output archive or manifest without --force returns exit code 3."""
        self.create_minimal_package()
        self.zip_path.write_bytes(b"EXISTING_ARCHIVE")

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
            force=False,
        )
        res = SubmissionPackager(cfg).run()

        self.assertFalse(res.success)
        self.assertEqual(res.exit_code, 3)
        self.assertEqual(self.zip_path.read_bytes(), b"EXISTING_ARCHIVE")

        # Now with force=True
        cfg.force = True
        res_force = SubmissionPackager(cfg).run()
        self.assertTrue(res_force.success)
        self.assertNotEqual(self.zip_path.read_bytes(), b"EXISTING_ARCHIVE")

    def test_source_immutability(self):
        """Source directory files and directory hash remain unchanged before and after packaging."""
        self.create_minimal_package()
        from local.packaging.packager import compute_directory_hash

        hash_before = compute_directory_hash(self.source_dir)

        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        res = SubmissionPackager(cfg).run()
        self.assertTrue(res.success)

        hash_after = compute_directory_hash(self.source_dir)
        self.assertEqual(hash_before, hash_after, "Source directory was mutated by packager!")


class TestCLIAndErrors(BasePackagingTestCase):
    """Tests CLI entrypoints, argument parsing, error codes, and JSON outputs."""

    def test_cli_help(self):
        """CLI --help exits 0 and prints usage."""
        with self.assertRaises(SystemExit) as cm:
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_out:
                cli_main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_cli_missing_source(self):
        """Omitting --source exits code 3."""
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_err:
            code = cli_main([])
            self.assertEqual(code, 3)
            self.assertIn("--source PATH is required", fake_err.getvalue())

    def test_cli_missing_source_json(self):
        """Omitting --source with --json outputs valid error JSON."""
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli_main(["--json"])
            self.assertEqual(code, 3)
            data = json.loads(fake_out.getvalue())
            self.assertFalse(data["success"])
            self.assertEqual(data["exit_code"], 3)

    def test_cli_nonexistent_source(self):
        """Passing nonexistent source directory returns exit code 3."""
        code = cli_main(["--source", str(Path(self.test_root) / "does_not_exist")])
        self.assertEqual(code, 3)


    def test_cli_check_only_mode(self):
        """--check-only mode validates and prints plan without writing files."""
        self.create_minimal_package()
        code = cli_main([
            "--source", str(self.source_dir),
            "--output", str(self.zip_path),
            "--manifest", str(self.manifest_path),
            "--check-only",
        ])
        self.assertEqual(code, 0)
        self.assertFalse(self.zip_path.exists())
        self.assertFalse(self.manifest_path.exists())

    def test_cli_json_output_schema(self):
        """--json output produces valid JSON conforming to the manifest schema."""
        self.create_minimal_package()
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli_main([
                "--source", str(self.source_dir),
                "--output", str(self.zip_path),
                "--manifest", str(self.manifest_path),
                "--json",
            ])
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())

            self.assertTrue(data["success"])
            self.assertEqual(data["exit_code"], 0)
            self.assertEqual(data["total_files_packaged"], 2)
            self.assertIn("archive_sha256", data)
            self.assertIn("manifest_data", data)
            manifest = data["manifest_data"]
            self.assertEqual(manifest["manifest_version"], "1.0.0")
            self.assertEqual(manifest["packager_version"], "1.0.0")
            self.assertIn("members", manifest)
            self.assertIn("validator_summary", manifest)

    def test_manifest_archive_consistency_verifier(self):
        """verify_manifest_archive_consistency detects tampering with archive members."""
        self.create_minimal_package()
        cfg = PackagerConfig(
            source_path=str(self.source_dir),
            output_path=str(self.zip_path),
            manifest_path=str(self.manifest_path),
        )
        res = SubmissionPackager(cfg).run()
        self.assertTrue(res.success)

        manifest_data = json.loads(self.manifest_path.read_text(encoding="utf-8"))

        # Clean check
        errors = verify_manifest_archive_consistency(self.zip_path, manifest_data)
        self.assertEqual(errors, [])

        # Tampered check (modify size in manifest)
        tampered_manifest = dict(manifest_data)
        tampered_manifest["members"] = [
            dict(m, size_bytes=m["size_bytes"] + 1) for m in manifest_data["members"]
        ]
        tampered_errors = verify_manifest_archive_consistency(self.zip_path, tampered_manifest)
        self.assertGreater(len(tampered_errors), 0)


class TestRealCandidatePackaging(unittest.TestCase):
    """Verifies dry-run and actual packaging determinism on repository candidate directories M0 through M5."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.candidates_dir = self.repo_root / "experiments" / "candidates"
        self.test_root = tempfile.mkdtemp(prefix="impulse_candidates_stage48_")

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def test_candidates_check_only_dry_runs(self):
        """All candidates M0 through M5 pass check-only dry runs with zero errors."""
        for cid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            c_path = self.candidates_dir / cid
            if not c_path.is_dir():
                continue

            cfg = PackagerConfig(
                source_path=str(c_path),
                check_only=True,
            )
            res = SubmissionPackager(cfg, repo_root=self.repo_root).run()
            self.assertTrue(res.success, f"Candidate {cid} check-only failed: {res.errors}")
            self.assertEqual(res.exit_code, 0)
            self.assertGreater(res.total_files_packaged, 0)
            self.assertEqual(res.candidate_id, cid)

    def test_candidate_m0_deterministic_packaging(self):
        """Packages candidate M0 twice and verifies exact SHA-256 byte identity and manifest consistency."""
        c_path = self.candidates_dir / "M0"
        if not c_path.is_dir():
            self.skipTest("Candidate M0 not found")

        out1 = Path(self.test_root) / "m0_run1"
        out2 = Path(self.test_root) / "m0_run2"
        out1.mkdir()
        out2.mkdir()

        zip1 = out1 / "submission.zip"
        man1 = out1 / "manifest.json"
        zip2 = out2 / "submission.zip"
        man2 = out2 / "manifest.json"

        cfg1 = PackagerConfig(source_path=str(c_path), output_path=str(zip1), manifest_path=str(man1))
        cfg2 = PackagerConfig(source_path=str(c_path), output_path=str(zip2), manifest_path=str(man2))

        res1 = SubmissionPackager(cfg1, repo_root=self.repo_root).run()
        res2 = SubmissionPackager(cfg2, repo_root=self.repo_root).run()

        self.assertTrue(res1.success, f"Run 1 failed: {res1.errors}")
        self.assertTrue(res2.success, f"Run 2 failed: {res2.errors}")

        self.assertEqual(res1.archive_sha256, res2.archive_sha256)
        self.assertEqual(zip1.read_bytes(), zip2.read_bytes())

        # Verify manifest consistency
        man1_data = json.loads(man1.read_text(encoding="utf-8"))
        errors = verify_manifest_archive_consistency(zip1, man1_data)
        self.assertEqual(errors, [])

    def test_candidate_m1_subagents_packaging(self):
        """Packages candidate M1 (which has multi-agent topology) and verifies sub-agents are packaged."""
        c_path = self.candidates_dir / "M1"
        if not c_path.is_dir():
            self.skipTest("Candidate M1 not found")

        out_dir = Path(self.test_root) / "m1_out"
        out_dir.mkdir()
        zip_path = out_dir / "submission.zip"
        man_path = out_dir / "manifest.json"

        cfg = PackagerConfig(source_path=str(c_path), output_path=str(zip_path), manifest_path=str(man_path))
        res = SubmissionPackager(cfg, repo_root=self.repo_root).run()

        self.assertTrue(res.success, f"Candidate M1 packaging failed: {res.errors}")
        self.assertTrue(zip_path.is_file())

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            self.assertIn("agent.yaml", names)
            subagent_entries = [n for n in names if n.startswith("sub_agents/")]
            self.assertGreater(len(subagent_entries), 0)


if __name__ == "__main__":
    unittest.main()


