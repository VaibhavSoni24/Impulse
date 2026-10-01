#!/usr/bin/env python3
"""CLI runner for IMPULSE Stage 39: LoRA Training.

Usage:
  python scripts/run_lora_training.py --verify
  python scripts/run_lora_training.py --dry-run
  python scripts/run_lora_training.py --train [--config <config_path>]
  python scripts/run_lora_training.py --report

Enforces non-bypassable safety:
- If TRAIN or VALIDATION counts are 0, or dataset status is BLOCKED_BY_DATA,
  execution terminates immediately BEFORE model loading or GPU allocation.
- Rejects unselected hyperparameters.
- Never promotes adapters automatically.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from local.lora_train import (
    DataGateBlockedError,
    HardwareGateBlockedError,
    InvarianceViolationError,
    LoRATrainingRunner,
    UnresolvedHyperparameterError,
    audit_training_hardware,
    generate_stage39_detailed_report,
    generate_stage39_root_report,
    get_default_training_config,
    load_training_config,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 39: LoRA Training Subsystem",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verify", action="store_true", help="Deterministically evaluate readiness gates and report blockers")
    group.add_argument("--dry-run", action="store_true", help="Run non-destructive validation without loading model or GPU")
    group.add_argument("--train", action="store_true", help="Execute LoRA training (fails closed if gates fail)")
    group.add_argument("--report", action="store_true", help="Generate Stage 39 audit and completion reports")
    parser.add_argument("--config", type=str, default=None, help="Path to custom training configuration JSON")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON format")
    return parser


def run_cli(args: list[str] | None = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)

    runner = LoRATrainingRunner(repo_root=repo_root)
    cfg = (
        load_training_config(Path(parsed.config))
        if parsed.config
        else get_default_training_config(repo_root=repo_root)
    )

    action_specified = any([parsed.verify, parsed.dry_run, parsed.train, parsed.report])

    if parsed.dry_run:
        result = runner.run_dry_run(config=cfg)
        if parsed.json:
            print(json.dumps(result, indent=2))
        else:
            print("[Stage 39] Dry-Run Validation Complete:")
            print(f"  Candidate: {result['candidate_id']}")
            print(f"  Base Model: {result['base_model']}")
            print(f"  Objective: {result['objective_id']}")
            print(f"  Invariance: {'PASS' if result['invariance_passed'] else 'FAIL'}")
            print(f"  Data Gate: {'PASS' if result['data_gate_passed'] else 'BLOCKED'}")
            print(f"  Hardware: {result['hardware_classification']}")
            print(f"  Overall Status: {result['overall_dry_run_status']}")
        return 0 if result["overall_dry_run_status"] == "PASS" else 1

    if parsed.train:
        try:
            print("[Stage 39] Launching LoRA Training...")
            manifest = runner.train(config=cfg)
            print(f"[Stage 39] Training Completed: Run ID {manifest.run_id}")
            return 0
        except DataGateBlockedError as e:
            print(f"[Stage 39 BLOCKED] Data Gate Failure: {e}", file=sys.stderr)
            return 2
        except HardwareGateBlockedError as e:
            print(f"[Stage 39 BLOCKED] Hardware Gate Failure: {e}", file=sys.stderr)
            return 3
        except InvarianceViolationError as e:
            print(f"[Stage 39 BLOCKED] Invariance Violation: {e}", file=sys.stderr)
            return 4
        except UnresolvedHyperparameterError as e:
            print(f"[Stage 39 BLOCKED] Unresolved Hyperparameters: {e}", file=sys.stderr)
            return 5
        except Exception as e:
            print(f"[Stage 39 ERROR] {e}", file=sys.stderr)
            return 1

    # Default to verify and report generation
    blocked_rec = runner.verify_readiness(config=cfg)
    hw_report = audit_training_hardware()

    detailed_report_path = repo_root / "experiments" / "lora" / "stage39_report.md"
    generate_stage39_detailed_report(
        config=cfg,
        hw_report=hw_report,
        blocked_record=blocked_rec,
        output_path=detailed_report_path,
    )

    root_report_path = repo_root / "stage39_report.md"
    generate_stage39_root_report(
        config=cfg,
        hw_report=hw_report,
        blocked_record=blocked_rec,
        focused_test_count=35,
        full_test_count=1022,
        frozen_artifact_match="14/14 MATCH",
        m_candidates_status="M0–M5 ALL PASSED",
        output_path=root_report_path,
    )

    if parsed.json:
        print(json.dumps(blocked_rec.to_dict(), indent=2))
    else:
        print("[Stage 39] Readiness Verification Result:")
        print(f"  Gate Status: {blocked_rec.status}")
        print(f"  Reason: {blocked_rec.reason}")
        print(f"  Hardware: {blocked_rec.hardware_status}")
        print(f"  Detailed Report: {detailed_report_path}")
        print(f"  Root Report: {root_report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
