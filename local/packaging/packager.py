"""IMPULSE Deterministic Submission Packaging Engine (Stage 48).

Builds byte-for-byte reproducible submission ZIP archives from validated
agent package directories, producing external reproducibility manifests and
verifying post-build archive integrity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Optional
import uuid
import zipfile

from local.packaging.config_validator import normalize_model_name, parse_simple_yaml
from local.packaging.constants import (
    DEFAULT_COMPRESS_LEVEL,
    FIXED_FILE_MODE,
    FIXED_ZIP_DATETIME,
    MANIFEST_SCHEMA_VERSION,
    PACKAGER_VERSION,
    PROHIBITED_DEV_DIRECTORIES,
    PROHIBITED_DEV_FILES,
    PROHIBITED_WEIGHT_EXTENSIONS,
)
from local.packaging.models import (
    CheckStatus,
    PackageValidationResult,
    PackagedMember,
    PackagerConfig,
    PackagerResult,
    ValidatorConfig,
)
from local.packaging.reader import normalize_rel_path
from local.packaging.validator import PackageValidator


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file deterministically in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_directory_hash(dir_path: Path) -> str:
    """Computes a lightweight content/metadata hash of a directory to verify immutability."""
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


def get_git_info(repo_root: Path) -> dict[str, Any]:
    """Extracts git commit and status metadata safely without failing in non-git environments."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return {
            "commit": commit,
            "dirty": len(status) > 0,
            "branch": branch,
        }
    except Exception:
        return {
            "commit": "unknown",
            "dirty": False,
            "branch": "unknown",
        }


def detect_candidate_metadata(source_dir: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Detects candidate_id, model, and agent name from package directory contents."""
    candidate_id: Optional[str] = None
    model_name: Optional[str] = None
    agent_name: Optional[str] = None

    # 1. Candidate ID from candidate manifest.json or directory parent
    cand_manifest = source_dir / "manifest.json"
    if cand_manifest.is_file():
        try:
            with open(cand_manifest, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "candidate_id" in data:
                    candidate_id = str(data["candidate_id"])
        except Exception:
            pass

    if not candidate_id:
        if source_dir.parent.name == "candidates":
            candidate_id = source_dir.name

    # 2. Model name and agent name from root agent.yaml
    root_yaml = source_dir / "agent.yaml"
    if not root_yaml.is_file():
        root_yaml = source_dir / "agent.yml"

    if root_yaml.is_file():
        try:
            with open(root_yaml, "r", encoding="utf-8") as f:
                parsed = parse_simple_yaml(f.read())
                if isinstance(parsed, dict):
                    if "model" in parsed and parsed["model"]:
                        model_name = normalize_model_name(str(parsed["model"]))
                    if "name" in parsed and parsed["name"]:
                        agent_name = str(parsed["name"])
        except Exception:
            pass

    return candidate_id, model_name, agent_name


def sanitize_path_for_manifest(path: Path, repo_root: Optional[Path] = None) -> str:
    """Normalizes a filesystem path for storage in manifest, removing host machine paths."""
    resolved = path.resolve()
    if repo_root is not None:
        try:
            rel = resolved.relative_to(repo_root.resolve())
            return rel.as_posix()
        except ValueError:
            pass
    return resolved.name


def resolve_relative_subpath(base_dir: str, rel_path: str) -> str:
    """Resolves relative include path inside package collapsing .. components."""
    clean_rel = rel_path.replace("\\", "/").strip("\"'")
    if base_dir:
        combined = f"{base_dir}/{clean_rel}"
    else:
        combined = clean_rel
    norm = os.path.normpath(combined).replace("\\", "/")
    return normalize_rel_path(norm)


def collect_source_files(
    source_dir: Path,
    output_zip_path: Optional[Path] = None,
    output_manifest_path: Optional[Path] = None,
) -> tuple[list[PackagedMember], list[dict[str, str]], list[str]]:
    """Recursively collects files to package from source directory while applying exclusions.

    Returns:
        (included_members, excluded_files, errors)
    """
    included: list[PackagedMember] = []
    excluded: list[dict[str, str]] = []
    errors: list[str] = []

    resolved_source = source_dir.resolve()
    resolved_zip = output_zip_path.resolve() if output_zip_path else None
    resolved_manifest = output_manifest_path.resolve() if output_manifest_path else None

    for root, dirs, files in os.walk(resolved_source, followlinks=False):
        current_dir = Path(root)

        if current_dir != resolved_source and current_dir.is_symlink():
            errors.append(f"Prohibited symlink directory detected: '{current_dir}'. Symlinks are forbidden.")
            continue

        pruned_dirs: list[str] = []
        for d in list(dirs):
            d_path = current_dir / d
            if d_path.is_symlink():
                errors.append(f"Prohibited symlink directory detected: '{d_path}'. Symlinks are forbidden.")
                pruned_dirs.append(d)
                continue

            if d in PROHIBITED_DEV_DIRECTORIES or d.startswith("."):
                try:
                    rel_d = d_path.relative_to(resolved_source).as_posix()
                except ValueError:
                    rel_d = d
                excluded.append({
                    "path": rel_d,
                    "reason": f"Directory '{d}' matches prohibited development directory rule",
                })
                pruned_dirs.append(d)

        for d in pruned_dirs:
            dirs.remove(d)

        for fname in sorted(files):
            f_path = current_dir / fname

            if f_path.is_symlink():
                errors.append(f"Prohibited symlink file detected: '{f_path}'. Symlinks are forbidden.")
                continue

            if resolved_zip and f_path.resolve() == resolved_zip:
                try:
                    rel_f = f_path.relative_to(resolved_source).as_posix()
                except ValueError:
                    rel_f = fname
                excluded.append({
                    "path": rel_f,
                    "reason": "Destination archive output path inside source directory",
                })
                continue

            if resolved_manifest and f_path.resolve() == resolved_manifest:
                try:
                    rel_f = f_path.relative_to(resolved_source).as_posix()
                except ValueError:
                    rel_f = fname
                excluded.append({
                    "path": rel_f,
                    "reason": "Destination manifest output path inside source directory",
                })
                continue

            try:
                rel_posix = f_path.relative_to(resolved_source).as_posix()
            except ValueError:
                errors.append(f"Unsafe path detected: '{f_path}' is outside source root. Escaping paths are forbidden.")
                continue


            if ".." in rel_posix.split("/") or rel_posix.startswith("/"):
                errors.append(f"Unsafe path detected: '{rel_posix}'. Escaping paths are forbidden.")
                continue

            if fname in PROHIBITED_DEV_FILES or fname.startswith("."):
                excluded.append({
                    "path": rel_posix,
                    "reason": f"File '{fname}' matches prohibited development file rule",
                })
                continue

            if re.match(r"^test_.*\.py$", fname, re.IGNORECASE) or re.match(r"^.*_test\.py$", fname, re.IGNORECASE):
                excluded.append({
                    "path": rel_posix,
                    "reason": f"File '{fname}' matches unit test exclusion rule",
                })
                continue

            if fname.lower().endswith(".log"):
                excluded.append({
                    "path": rel_posix,
                    "reason": f"File '{fname}' is a log file",
                })
                continue

            if fname.lower().endswith((".pyc", ".pyo", ".pyd")):
                excluded.append({
                    "path": rel_posix,
                    "reason": f"File '{fname}' is compiled Python bytecode",
                })
                continue

            f_suffix = Path(fname).suffix.lower()
            if f_suffix in PROHIBITED_WEIGHT_EXTENSIONS:
                excluded.append({
                    "path": rel_posix,
                    "reason": f"File '{fname}' uses prohibited binary/pickle weight extension '{f_suffix}'",
                })
                continue

            try:
                size = f_path.stat().st_size
                sha = compute_file_sha256(f_path)
                included.append(
                    PackagedMember(
                        posix_path=rel_posix,
                        source_abs_path=str(f_path.resolve()),
                        size_bytes=size,
                        sha256=sha,
                    )
                )
            except Exception as e:
                errors.append(f"Failed to read/hash file '{f_path}': {e}")

    root_configs = [m for m in included if m.posix_path in ("agent.yaml", "agent.yml")]
    if not root_configs:
        errors.append("Package missing required root configuration 'agent.yaml' (or 'agent.yml') at archive root.")

    included.sort(key=lambda m: m.posix_path)

    return included, excluded, errors


def verify_required_dependencies(
    members: list[PackagedMember],
    source_dir: Path,
) -> list[str]:
    """Verifies that all files declared/included by the agent configuration exist in packaged members."""
    member_paths = {m.posix_path for m in members}
    errors: list[str] = []

    root_config = "agent.yaml" if "agent.yaml" in member_paths else "agent.yml"
    root_path = source_dir / root_config
    if not root_path.is_file():
        return [f"Root config '{root_config}' is missing."]

    configs_to_visit = [root_config]
    visited_configs: set[str] = set()

    include_pattern = re.compile(r"!include\s+([^\s\r\n#]+)")

    while configs_to_visit:
        cfg = configs_to_visit.pop(0)
        if cfg in visited_configs:
            continue
        visited_configs.add(cfg)

        cfg_file = source_dir / cfg
        if not cfg_file.is_file():
            errors.append(f"Required configuration file '{cfg}' is missing from package.")
            continue

        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            errors.append(f"Could not read config file '{cfg}': {e}")
            continue

        parent_posix = str(PurePosixPath(cfg).parent)
        if parent_posix == ".":
            parent_posix = ""

        for match in include_pattern.finditer(content):
            inc_target = match.group(1).strip("'\"")
            norm_inc = resolve_relative_subpath(parent_posix, inc_target)

            if norm_inc not in member_paths:
                errors.append(f"Configuration '{cfg}' references missing include target '{norm_inc}'.")
            elif norm_inc.endswith((".yaml", ".yml")):
                configs_to_visit.append(norm_inc)


        try:
            parsed = parse_simple_yaml(content)
            if isinstance(parsed, dict):
                sub_agents = parsed.get("sub_agents")
                if isinstance(sub_agents, list):
                    for sa in sub_agents:
                        if isinstance(sa, str) and not sa.startswith("!include"):
                            norm_sa = normalize_rel_path(sa)
                            if norm_sa not in member_paths:
                                errors.append(f"Declared sub-agent '{norm_sa}' is missing from package.")
                            elif norm_sa.endswith((".yaml", ".yml")):
                                configs_to_visit.append(norm_sa)

                skills = parsed.get("skills")
                if isinstance(skills, list):
                    for sk in skills:
                        if isinstance(sk, str):
                            norm_sk = normalize_rel_path(sk)
                            skill_manifest = f"{norm_sk}/SKILL.md"
                            if skill_manifest not in member_paths:
                                errors.append(f"Declared skill '{norm_sk}' missing 'SKILL.md' manifest in package.")

                adapters = parsed.get("adapters")
                if isinstance(adapters, list):
                    for ad in adapters:
                        if isinstance(ad, str):
                            norm_ad = normalize_rel_path(ad)
                            cfg_path = f"{norm_ad}/adapter_config.json"
                            weight_path = f"{norm_ad}/adapter_model.safetensors"
                            if cfg_path not in member_paths:
                                errors.append(f"Declared adapter '{norm_ad}' missing 'adapter_config.json' in package.")
                            if weight_path not in member_paths:
                                errors.append(f"Declared adapter '{norm_ad}' missing 'adapter_model.safetensors' in package.")
        except Exception:
            pass

    return errors


def build_manifest(
    config: PackagerConfig,
    members: list[PackagedMember],
    excluded_files: list[dict[str, str]],
    archive_sha256: str,
    archive_size_bytes: int,
    candidate_id: Optional[str],
    base_model: Optional[str],
    agent_name: Optional[str],
    validator_result: Optional[PackageValidationResult],
    repo_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Constructs the versioned reproducibility manifest data structure."""
    val_summary = {
        "overall_valid": validator_result.overall_valid if validator_result else False,
        "checks_executed": validator_result.checks_executed if validator_result else 0,
        "passed": validator_result.passed_count if validator_result else 0,
        "failed": validator_result.failed_count if validator_result else 0,
        "warnings": validator_result.warnings_count if validator_result else 0,
        "skipped": validator_result.skipped_count if validator_result else 0,
        "unavailable": validator_result.unavailable_count if validator_result else 0,
    }

    fixed_ts_iso = datetime(*config.fixed_timestamp, tzinfo=timezone.utc).isoformat()

    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_SCHEMA_VERSION,
        "packager_version": PACKAGER_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": {
            "relative_path": sanitize_path_for_manifest(Path(config.source_path), repo_root),
            "source_dir_name": Path(config.source_path).resolve().name,
            "candidate_id": candidate_id,
        },
        "git_info": get_git_info(repo_root or Path.cwd()),
        "package_metadata": {
            "base_model": base_model,
            "agent_name": agent_name,
            "root_config": "agent.yaml",
        },
        "archive": {
            "filename": Path(config.output_path).name,
            "sha256": archive_sha256,
            "byte_size": archive_size_bytes,
            "deterministic_settings": {
                "fixed_timestamp": fixed_ts_iso,
                "compression": "deflated",
                "compresslevel": config.compresslevel,
                "file_mode": "0644",
                "sort_order": "lexicographical_posix",
            },
        },
        "members": [m.to_dict() for m in members],
        "aggregates": {
            "total_files": len(members),
            "total_uncompressed_bytes": sum(m.size_bytes for m in members),
        },
        "validator_summary": val_summary,
        "excluded_files": excluded_files,
        "build_outcome": "SUCCESS",
        "notes": "Declarative YAML package verified. Official compiler check unavailable locally (proprietary Kaggle runner image).",
    }
    return manifest


def verify_manifest_archive_consistency(
    archive_path: Path,
    manifest_data: dict[str, Any],
) -> list[str]:
    """Verifies that the generated archive's internal members match the manifest data exactly."""
    errors: list[str] = []

    computed_sha = compute_file_sha256(archive_path)
    recorded_sha = manifest_data.get("archive", {}).get("sha256")
    if computed_sha != recorded_sha:
        errors.append(f"Archive SHA-256 mismatch: recorded {recorded_sha}, computed {computed_sha}.")

    computed_size = archive_path.stat().st_size
    recorded_size = manifest_data.get("archive", {}).get("byte_size")
    if computed_size != recorded_size:
        errors.append(f"Archive size mismatch: recorded {recorded_size}, computed {computed_size}.")

    manifest_members = {m["path"]: m for m in manifest_data.get("members", [])}

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            infolist = zf.infolist()
            zf_members = {info.filename: info for info in infolist}

            if len(zf_members) != len(manifest_members):
                errors.append(
                    f"Member count mismatch: archive has {len(zf_members)}, manifest has {len(manifest_members)}."
                )

            for path, m_data in manifest_members.items():
                if path not in zf_members:
                    errors.append(f"Member '{path}' present in manifest but missing from archive.")
                    continue

                info = zf_members[path]
                if info.file_size != m_data["size_bytes"]:
                    errors.append(
                        f"Member '{path}' size mismatch: archive has {info.file_size}, manifest has {m_data['size_bytes']}."
                    )

                raw_bytes = zf.read(path)
                member_sha = hashlib.sha256(raw_bytes).hexdigest()
                if member_sha != m_data["sha256"]:
                    errors.append(
                        f"Member '{path}' SHA-256 mismatch: archive has {member_sha}, manifest has {m_data['sha256']}."
                    )

            for path in zf_members:
                if path not in manifest_members:
                    errors.append(f"Unexpected member '{path}' in archive not recorded in manifest.")
    except Exception as e:
        errors.append(f"Could not open archive for consistency verification: {e}")

    return errors


class SubmissionPackager:
    """Orchestrates deterministic submission package creation and validation."""

    def __init__(self, config: PackagerConfig, repo_root: Optional[Path] = None) -> None:
        self.config = config
        self.source_path = Path(config.source_path).resolve()
        self.output_path = Path(config.output_path).resolve()
        self.manifest_path = Path(config.manifest_path).resolve()
        self.repo_root = (repo_root or Path.cwd()).resolve()

    def run(self) -> PackagerResult:
        """Executes the deterministic packaging lifecycle."""
        errors: list[str] = []
        warnings: list[str] = []

        if not self.source_path.exists():
            return PackagerResult(
                success=False,
                exit_code=3,
                source_path=str(self.source_path),
                errors=[f"Source package directory does not exist: {self.source_path}"],
            )

        if not self.source_path.is_dir():
            return PackagerResult(
                success=False,
                exit_code=3,
                source_path=str(self.source_path),
                errors=[f"Source path is not a directory: {self.source_path}"],
            )

        if not self.config.check_only:
            if self.output_path.exists() and not self.config.force:
                return PackagerResult(
                    success=False,
                    exit_code=3,
                    source_path=str(self.source_path),
                    output_path=str(self.output_path),
                    manifest_path=str(self.manifest_path),
                    errors=[f"Output archive already exists: '{self.output_path}'. Use --force to overwrite."],
                )
            if self.manifest_path.exists() and not self.config.force:
                return PackagerResult(
                    success=False,
                    exit_code=3,
                    source_path=str(self.source_path),
                    output_path=str(self.output_path),
                    manifest_path=str(self.manifest_path),
                    errors=[f"Output manifest already exists: '{self.manifest_path}'. Use --force to overwrite."],
                )

        source_hash_before = compute_directory_hash(self.source_path)

        # 3. File collection and exclusion
        members, excluded_files, collection_errors = collect_source_files(
            source_dir=self.source_path,
            output_zip_path=self.output_path,
            output_manifest_path=self.manifest_path,
        )

        if collection_errors:
            return PackagerResult(
                success=False,
                exit_code=1,
                source_path=str(self.source_path),
                excluded_files=excluded_files,
                errors=collection_errors,
            )

        # 4. Pre-packaging Source Validation
        source_validator = PackageValidator(
            self.source_path,
            ValidatorConfig(
                strict_mode=self.config.strict_mode,
                ignore_excluded_dev_files=True,
            ),
        )

        source_val_result = source_validator.validate()

        if not source_val_result.overall_valid:
            failures = [f"{c.check_id}: {c.diagnostic}" for c in source_val_result.get_failures()]
            return PackagerResult(
                success=False,
                exit_code=1,
                source_path=str(self.source_path),
                source_validation=source_val_result,
                excluded_files=excluded_files,
                errors=["Source package validation failed:"] + failures,
            )

        for w in source_val_result.get_warnings():
            warnings.append(f"{w.check_id}: {w.diagnostic}")


        dep_errors = verify_required_dependencies(members, self.source_path)
        if dep_errors:
            return PackagerResult(
                success=False,
                exit_code=1,
                source_path=str(self.source_path),
                source_validation=source_val_result,
                excluded_files=excluded_files,
                errors=dep_errors,
                warnings=warnings,
            )

        candidate_id, base_model, agent_name = detect_candidate_metadata(self.source_path)

        total_files = len(members)
        total_uncompressed = sum(m.size_bytes for m in members)

        if self.config.check_only:
            source_hash_after = compute_directory_hash(self.source_path)
            if source_hash_before != source_hash_after:
                return PackagerResult(
                    success=False,
                    exit_code=1,
                    source_path=str(self.source_path),
                    errors=["Source directory mutated during check-only run."],
                )

            mock_manifest = build_manifest(
                config=self.config,
                members=members,
                excluded_files=excluded_files,
                archive_sha256="<check_only_dry_run>",
                archive_size_bytes=0,
                candidate_id=candidate_id,
                base_model=base_model,
                agent_name=agent_name,
                validator_result=source_val_result,
                repo_root=self.repo_root,
            )

            return PackagerResult(
                success=True,
                exit_code=0,
                source_path=str(self.source_path),
                output_path=str(self.output_path),
                manifest_path=str(self.manifest_path),
                archive_sha256=None,
                archive_size_bytes=0,
                total_files_packaged=total_files,
                total_uncompressed_bytes=total_uncompressed,
                candidate_id=candidate_id,
                base_model=base_model,
                agent_name=agent_name,
                source_validation=source_val_result,
                excluded_files=excluded_files,
                warnings=warnings,
                manifest_data=mock_manifest,
            )

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        staging_suffix = uuid.uuid4().hex[:8]
        temp_zip = self.output_path.with_name(f"{self.output_path.stem}.tmp_{os.getpid()}_{staging_suffix}.zip")
        temp_manifest = self.manifest_path.with_name(f"{self.manifest_path.stem}.tmp_{os.getpid()}_{staging_suffix}.json")

        try:
            with zipfile.ZipFile(
                temp_zip,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=self.config.compresslevel,
            ) as zf:
                zf.comment = b""

                for member in members:
                    zinfo = zipfile.ZipInfo(
                        filename=member.posix_path,
                        date_time=self.config.fixed_timestamp,
                    )
                    zinfo.compress_type = zipfile.ZIP_DEFLATED
                    zinfo.create_system = 3  # Unix
                    zinfo.external_attr = FIXED_FILE_MODE << 16
                    zinfo.comment = b""

                    with open(member.source_abs_path, "rb") as f:
                        data = f.read()

                    zf.writestr(
                        zinfo,
                        data,
                        compress_type=zipfile.ZIP_DEFLATED,
                        compresslevel=self.config.compresslevel,
                    )

            archive_sha256 = compute_file_sha256(temp_zip)
            archive_size = temp_zip.stat().st_size

            archive_validator = PackageValidator(
                temp_zip,
                ValidatorConfig(strict_mode=self.config.strict_mode),
            )
            archive_val_result = archive_validator.validate()

            if not archive_val_result.overall_valid:
                failures = [f"{c.check_id}: {c.diagnostic}" for c in archive_val_result.get_failures()]
                return PackagerResult(
                    success=False,
                    exit_code=2,
                    source_path=str(self.source_path),
                    output_path=str(self.output_path),
                    manifest_path=str(self.manifest_path),
                    source_validation=source_val_result,
                    archive_validation=archive_val_result,
                    excluded_files=excluded_files,
                    errors=["Post-packaging archive verification failed:"] + failures,
                    warnings=warnings,
                )

            manifest_data = build_manifest(
                config=self.config,
                members=members,
                excluded_files=excluded_files,
                archive_sha256=archive_sha256,
                archive_size_bytes=archive_size,
                candidate_id=candidate_id,
                base_model=base_model,
                agent_name=agent_name,
                validator_result=archive_val_result,
                repo_root=self.repo_root,
            )

            consistency_errors = verify_manifest_archive_consistency(temp_zip, manifest_data)
            if consistency_errors:
                return PackagerResult(
                    success=False,
                    exit_code=2,
                    source_path=str(self.source_path),
                    output_path=str(self.output_path),
                    manifest_path=str(self.manifest_path),
                    source_validation=source_val_result,
                    archive_validation=archive_val_result,
                    excluded_files=excluded_files,
                    errors=["Archive manifest consistency check failed:"] + consistency_errors,
                    warnings=warnings,
                )

            with open(temp_manifest, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)

            os.replace(temp_zip, self.output_path)
            os.replace(temp_manifest, self.manifest_path)

            source_hash_after = compute_directory_hash(self.source_path)
            if source_hash_before != source_hash_after:
                return PackagerResult(
                    success=False,
                    exit_code=1,
                    source_path=str(self.source_path),
                    output_path=str(self.output_path),
                    manifest_path=str(self.manifest_path),
                    errors=["Source directory mutated during packaging."],
                )

            return PackagerResult(
                success=True,
                exit_code=0,
                source_path=str(self.source_path),
                output_path=str(self.output_path),
                manifest_path=str(self.manifest_path),
                archive_sha256=archive_sha256,
                archive_size_bytes=archive_size,
                total_files_packaged=total_files,
                total_uncompressed_bytes=total_uncompressed,
                candidate_id=candidate_id,
                base_model=base_model,
                agent_name=agent_name,
                source_validation=source_val_result,
                archive_validation=archive_val_result,
                excluded_files=excluded_files,
                warnings=warnings,
                manifest_data=manifest_data,
            )

        finally:
            if temp_zip.exists():
                try:
                    temp_zip.unlink()
                except Exception:
                    pass
            if temp_manifest.exists():
                try:
                    temp_manifest.unlink()
                except Exception:
                    pass
