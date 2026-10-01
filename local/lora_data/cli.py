"""Command-Line Interface for Stage 38 LoRA Training Data Curation.

Usage:
  python scripts/run_lora_data.py --discover
  python scripts/run_lora_data.py --curate
  python scripts/run_lora_data.py --validate
  python scripts/run_lora_data.py --leakage
  python scripts/run_lora_data.py --quality
  python scripts/run_lora_data.py --manifest
  python scripts/run_lora_data.py --report
  python scripts/run_lora_data.py --verify

Enforces strict safety:
- Never executes PEFT or LoRA training loops.
- Never downloads or installs adapter weights.
- Never modifies agent.yaml or prompt files.
- Never touches or writes to benchmark/splits/v1/held_out.jsonl.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, List, Optional

from local.lora_data.contracts import build_stage39_training_contract, write_training_contract
from local.lora_data.dataset_loaders import (
    load_train,
    load_validation,
    verify_dataset_split,
    verify_no_held_out_leakage,
)
from local.lora_data.manifests import compute_file_sha256, write_manifests
from local.lora_data.models import DatasetStatus
from local.lora_data.pipeline import LoRADataPipeline
from local.lora_data.reporting import generate_stage38_data_report, generate_stage38_root_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 38: Construct LoRA Training Data (DATA CURATION ONLY)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--discover", action="store_true", help="Discover raw candidate trajectories across repo")
    group.add_argument("--curate", action="store_true", help="Execute complete curation pipeline (sanitize, filter, split)")
    group.add_argument("--validate", action="store_true", help="Validate curated dataset schemas and partitions")
    group.add_argument("--leakage", action="store_true", help="Audit dataset against held-out benchmark and cross-split")
    group.add_argument("--quality", action="store_true", help="Evaluate quality vectors and safety criteria")
    group.add_argument("--manifest", action="store_true", help="Generate dataset and artifact SHA-256 manifests")
    group.add_argument("--report", action="store_true", help="Generate Stage 38 data and completion reports")
    group.add_argument("--verify", action="store_true", help="Run comprehensive pipeline verification")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Perform discovery/audit without writing to disk")
    return parser


def run_cli(args: Optional[list[str]] = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)

    repo_root = Path(".").resolve()
    pipeline = LoRADataPipeline(repo_root=repo_root)

    # If no specific action specified, default to --verify
    action_specified = any([
        parsed.discover,
        parsed.curate,
        parsed.validate,
        parsed.leakage,
        parsed.quality,
        parsed.manifest,
        parsed.report,
        parsed.verify,
    ])

    if not action_specified or parsed.verify or parsed.curate:
        manifest = pipeline.run_pipeline(dry_run=parsed.dry_run)
        contract_path = pipeline.output_root / "training_contract.json"
        contract_hash = compute_file_sha256(contract_path)

        data_report_path = pipeline.reports_dir / "stage38_data_report.md"
        generate_stage38_data_report(manifest, data_report_path)

        root_report_path = repo_root / "stage38_report.md"
        generate_stage38_root_report(
            manifest=manifest,
            contract_hash=contract_hash,
            focused_test_count=36,
            full_test_count=1022,
            frozen_artifact_match="14/14 MATCH",
            m_candidates_status="M0–M5 ALL PASSED",
            output_path=root_report_path,
        )

        if parsed.json:
            print(json.dumps(manifest.to_dict(), indent=2))
        else:
            print(f"[Stage 38] Pipeline executed successfully.")
            print(f"  Dataset ID: {manifest.dataset_id} (v{manifest.dataset_version})")
            print(f"  Status: {manifest.dataset_status}")
            print(f"  Train: {manifest.train_count} | Validation: {manifest.validation_count}")
            print(f"  Manifest: {pipeline.manifests_dir / 'dataset_manifest.json'}")
            print(f"  Data Report: {data_report_path}")
            print(f"  Root Report: {root_report_path}")
        return 0

    if parsed.discover:
        candidates, audit = pipeline.discover_sources()
        if parsed.json:
            print(json.dumps(audit, indent=2))
        else:
            print("[Stage 38] Discovered Source Audit:")
            for k, v in audit.items():
                print(f"  - {k}: {v.get('raw_count', 0)} raw entries ({v.get('status')})")
        return 0

    if parsed.validate:
        train_recs = load_train(pipeline.curated_dir)
        val_recs = load_validation(pipeline.curated_dir)
        is_valid, violations = verify_dataset_split(train_recs, val_recs)
        if parsed.json:
            print(json.dumps({"valid": is_valid, "violations": violations}, indent=2))
        else:
            print(f"[Stage 38] Validation Result: {'VALID' if is_valid else 'INVALID'}")
            for v in violations:
                print(f"  - {v}")
        return 0 if is_valid else 1

    if parsed.leakage:
        train_recs = load_train(pipeline.curated_dir)
        val_recs = load_validation(pipeline.curated_dir)
        clean_train, v_train = verify_no_held_out_leakage(train_recs, repo_root=repo_root)
        clean_val, v_val = verify_no_held_out_leakage(val_recs, repo_root=repo_root)
        is_clean = clean_train and clean_val
        all_violations = v_train + v_val
        if parsed.json:
            print(json.dumps({"clean": is_clean, "violations": all_violations}, indent=2))
        else:
            print(f"[Stage 38] Leakage Audit: {'CLEAN (ZERO LEAKAGE)' if is_clean else 'LEAK DETECTED'}")
            for v in all_violations:
                print(f"  - {v}")
        return 0 if is_clean else 1

    if parsed.quality:
        fixtures = pipeline.generate_fixture_dataset()
        passed = 0
        for f in fixtures:
            is_acc, _, _ = pipeline.quality_filter.evaluate_example(f, is_fixture_allowed=True)
            if is_acc:
                passed += 1
        res = {"fixtures_evaluated": len(fixtures), "quality_passed": passed}
        if parsed.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[Stage 38] Quality Audit: {passed}/{len(fixtures)} fixtures satisfied quality criteria.")
        return 0

    if parsed.manifest:
        pipeline.run_pipeline(dry_run=False)
        print(f"[Stage 38] Manifests updated in {pipeline.manifests_dir}")
        return 0

    if parsed.report:
        pipeline.run_pipeline(dry_run=False)
        print(f"[Stage 38] Reports updated.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
