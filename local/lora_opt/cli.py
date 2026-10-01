"""Command-Line Interface for LoRA Feasibility / Readiness Study (Stage 37 Section 20).

Provides commands:
- `--verify`: verify architecture, benchmark, prompt, tool, and hardware readiness
- `--report`: display or generate L0 feasibility report
- `--hardware`: display host hardware and ML runtime capability audit
- `--objectives`: display candidate and selected LoRA training objectives
- `--contract`: display controlled LoRA experiment contract for Stage 39
- `--setup`: generate baseline snapshot, contract, manifest, and report artifacts
- `--json`: machine-readable JSON output
- `--dry-run`: read-only execution without filesystem writes
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from local.lora_opt.architecture_stability import verify_architecture_stability
from local.lora_opt.baseline import capture_baseline_snapshot
from local.lora_opt.benchmark_stability import verify_benchmark_stability
from local.lora_opt.experiment_contract import (
    build_experiment_contract,
    build_no_adapter_control,
)
from local.lora_opt.failure_readiness import audit_failure_taxonomy
from local.lora_opt.hardware_audit import run_hardware_audit
from local.lora_opt.models import (
    L0Decision,
    ObjectiveStatus,
    ReadinessDimensionStatus,
)
from local.lora_opt.objectives import (
    get_candidate_objectives,
    select_objectives,
)
from local.lora_opt.prompt_stability import verify_root_prompt_stability
from local.lora_opt.reporting import (
    build_l0_manifest,
    determine_l0_decision,
    generate_l0_report,
    generate_stage37_report,
)
from local.lora_opt.tool_contracts import verify_tool_contracts


def run_lora_cli(argv: Optional[List[str]] = None) -> int:
    """CLI driver for the LoRA Feasibility Study (L0)."""
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 37: LoRA Feasibility / Readiness Study CLI"
    )
    parser.add_argument("--verify", action="store_true", help="Verify all readiness dimensions and artifacts")
    parser.add_argument("--report", action="store_true", help="Display L0 feasibility report")
    parser.add_argument("--hardware", action="store_true", help="Display host hardware and runtime audit")
    parser.add_argument("--objectives", action="store_true", help="Display candidate and selected LoRA objectives")
    parser.add_argument("--contract", action="store_true", help="Display Stage 39 controlled experiment contract")
    parser.add_argument("--setup", action="store_true", help="Generate all L0 baseline and report artifacts")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--dry-run", action="store_true", help="Read-only execution without writing files")

    args = parser.parse_args(argv)
    repo_root = Path.cwd()

    # Default action if none specified is --verify
    if not any([args.verify, args.report, args.hardware, args.objectives, args.contract, args.setup]):
        args.verify = True

    # 1. Hardware audit
    if args.hardware:
        hw = run_hardware_audit()
        if args.json:
            print(json.dumps(hw.to_dict(), indent=2))
        else:
            print(f"# IMPULSE Host Hardware & Runtime Feasibility Audit")
            print(f"- OS: {hw.os_name} {hw.os_release}")
            print(f"- Python: {hw.python_version}")
            print(f"- System RAM: {hw.total_ram_gb:.2f} GB total")
            print(f"- Available Disk: {hw.free_disk_gb:.2f} GB")
            print(f"- CUDA Available: {hw.cuda_available}")
            print(f"- GPU Count: {hw.gpu_count}")
            print(f"- GPU Device: {hw.gpu_model or 'None'}")
            print(f"- Per-GPU VRAM: {hw.per_gpu_vram_gb if hw.per_gpu_vram_gb else 'N/A'}")
            print(f"- PyTorch: {hw.torch_version or 'NOT INSTALLED'}")
            print(f"- Transformers: {hw.transformers_version or 'NOT INSTALLED'}")
            print(f"- PEFT: {hw.peft_version or 'NOT INSTALLED'}")
            print(f"- Classification: {hw.classification}")
            print(f"- Feasibility Notes: {hw.rationale}")
        return 0

    # 2. Objectives
    if args.objectives:
        candidates = get_candidate_objectives()
        primary, secondary = select_objectives(candidates)
        if args.json:
            out = {
                "candidates": [c.to_dict() for c in candidates],
                "selected_primary": primary.to_dict() if primary else None,
                "selected_secondary": secondary.to_dict() if secondary else None,
            }
            print(json.dumps(out, indent=2))
        else:
            print(f"# IMPULSE Stage 37 Candidate LoRA Objectives")
            for c in candidates:
                print(f"\n## [{c.objective_id}] {c.name}")
                print(f"- Status: {c.status}")
                print(f"- Problem: {c.problem_definition}")
                print(f"- Target Classes: {c.target_failure_classes}")
                print(f"- Desired: {c.desired_behavior}")
                print(f"- Undesired: {c.undesired_behavior}")
                print(f"- Metric: {c.evaluation_metric}")
            print("\n==================================================")
            print(f"Selected Primary: {primary.objective_id if primary else 'NONE'}")
            print(f"Selected Secondary: {secondary.objective_id if secondary else 'NONE'}")
        return 0

    # 3. Contract
    if args.contract:
        candidates = get_candidate_objectives()
        primary, _ = select_objectives(candidates)
        assert primary is not None
        contract = build_experiment_contract(repo_root=repo_root, primary_obj=primary)
        control = build_no_adapter_control(repo_root=repo_root)
        out = {
            "experiment_contract": contract.to_dict(),
            "no_adapter_control": control,
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(json.dumps(out, indent=2))
        return 0

    # 4. Setup / Artifact Generation
    if args.setup:
        l0_dir = repo_root / "experiments" / "lora" / "L0"
        baseline_dir = l0_dir / "baseline"
        if not args.dry_run:
            baseline_dir.mkdir(parents=True, exist_ok=True)

        # Snapshot
        snapshot = capture_baseline_snapshot(repo_root=repo_root)
        snapshot_file = baseline_dir / "snapshot.json"
        if not args.dry_run:
            snapshot_file.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")

        # Contract
        candidates = get_candidate_objectives()
        primary, secondary = select_objectives(candidates)
        assert primary is not None
        contract = build_experiment_contract(repo_root=repo_root, primary_obj=primary)
        contract_file = l0_dir / "experiment_contract.json"
        if not args.dry_run:
            contract_file.write_text(json.dumps(contract.to_dict(), indent=2), encoding="utf-8")

        # Manifest
        hw = run_hardware_audit()
        arch = verify_architecture_stability(repo_root=repo_root)
        bm = verify_benchmark_stability(repo_root=repo_root)
        pm = verify_root_prompt_stability(repo_root=repo_root)
        tc_dict = verify_tool_contracts(repo_root=repo_root)
        decision = determine_l0_decision(arch=arch, bm=bm, pm=pm, tc_dict=tc_dict, primary_obj=primary, hw=hw)

        manifest = build_l0_manifest(
            repo_root=repo_root,
            snapshot=snapshot,
            contract=contract,
            primary_obj=primary,
            decision=decision,
            hw=hw,
        )
        manifest_file = l0_dir / "manifest.json"
        if not args.dry_run:
            manifest_file.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

        # Report
        report_md = generate_l0_report(
            repo_root=repo_root,
            snapshot=snapshot,
            arch=arch,
            bm=bm,
            pm=pm,
            tc_dict=tc_dict,
            hw=hw,
            candidates=candidates,
            primary=primary,
            secondary=secondary,
            contract=contract,
            decision=decision,
        )
        report_file = l0_dir / "report.md"
        if not args.dry_run:
            report_file.write_text(report_md, encoding="utf-8")

        # Top-level stage37_report.md
        stage37_md = generate_stage37_report(
            repo_root=repo_root,
            snapshot=snapshot,
            arch=arch,
            bm=bm,
            pm=pm,
            tc_dict=tc_dict,
            hw=hw,
            candidates=candidates,
            primary=primary,
            secondary=secondary,
            contract=contract,
            decision=decision,
        )
        stage37_file = repo_root / "stage37_report.md"
        if not args.dry_run:
            stage37_file.write_text(stage37_md, encoding="utf-8")

        if args.json:
            print(json.dumps({
                "status": "SUCCESS",
                "l0_dir": str(l0_dir),
                "decision": decision.value,
                "primary_objective": primary.objective_id,
            }, indent=2))
        else:
            print(f"[SUCCESS] L0 artifacts generated at: {l0_dir}")
            print(f"- Baseline Snapshot: {snapshot_file}")
            print(f"- Experiment Contract: {contract_file}")
            print(f"- Manifest: {manifest_file}")
            print(f"- L0 Report: {report_file}")
            print(f"- Stage 37 Report: {stage37_file}")
            print(f"- Decision: {decision.value}")
        return 0

    # 5. Report view
    if args.report:
        report_file = repo_root / "experiments" / "lora" / "L0" / "report.md"
        if not report_file.exists():
            # Generate dynamically
            snapshot = capture_baseline_snapshot(repo_root=repo_root)
            arch = verify_architecture_stability(repo_root=repo_root)
            bm = verify_benchmark_stability(repo_root=repo_root)
            pm = verify_root_prompt_stability(repo_root=repo_root)
            tc_dict = verify_tool_contracts(repo_root=repo_root)
            hw = run_hardware_audit()
            candidates = get_candidate_objectives()
            primary, secondary = select_objectives(candidates)
            contract = build_experiment_contract(repo_root=repo_root, primary_obj=primary) if primary else None
            decision = determine_l0_decision(arch=arch, bm=bm, pm=pm, tc_dict=tc_dict, primary_obj=primary, hw=hw)
            report_md = generate_l0_report(
                repo_root=repo_root,
                snapshot=snapshot,
                arch=arch,
                bm=bm,
                pm=pm,
                tc_dict=tc_dict,
                hw=hw,
                candidates=candidates,
                primary=primary,
                secondary=secondary,
                contract=contract,
                decision=decision,
            )
        else:
            report_md = report_file.read_text(encoding="utf-8")

        if args.json:
            print(json.dumps({"path": str(report_file), "content": report_md}, indent=2))
        else:
            print(report_md)
        return 0

    # 6. Verify (default)
    if args.verify:
        arch = verify_architecture_stability(repo_root=repo_root)
        bm = verify_benchmark_stability(repo_root=repo_root)
        pm = verify_root_prompt_stability(repo_root=repo_root)
        tc_dict = verify_tool_contracts(repo_root=repo_root)
        hw = run_hardware_audit()
        candidates = get_candidate_objectives()
        primary, _ = select_objectives(candidates)
        decision = determine_l0_decision(arch=arch, bm=bm, pm=pm, tc_dict=tc_dict, primary_obj=primary, hw=hw)

        arch_ok = str(arch.overall_status) in ("STABLE", "READY")
        bm_ok = str(bm.status) == "BENCHMARK_STABLE"
        pm_ok = str(pm.status) == "STABLE"
        tc_ok = all(str(r.status) == "STABLE" for r in tc_dict.values())
        all_ok = arch_ok and bm_ok and pm_ok and tc_ok and (primary is not None)

        dec_str = decision.value if hasattr(decision, "value") else str(decision)
        hw_str = hw.classification.value if hasattr(hw.classification, "value") else str(hw.classification)

        out = {
            "overall_status": "PASS" if all_ok else "FAIL",
            "decision": dec_str,
            "architecture_stability": str(arch.overall_status),
            "benchmark_stability": str(bm.status),
            "prompt_stability": str(pm.status),
            "tool_contracts_stable": tc_ok,
            "selected_objective": primary.objective_id if primary else "NONE",
            "infrastructure": hw_str,
        }

        if args.json:
            print(json.dumps(out, indent=2))
        else:
            status_str = "[PASS]" if all_ok else "[FAIL]"
            print(f"{status_str} IMPULSE Stage 37 LoRA Feasibility Audit:")
            print(f"  - Decision: {dec_str}")
            print(f"  - Architecture Stability: {arch.overall_status}")
            print(f"  - Benchmark Stability: {bm.status}")
            print(f"  - Prompt Stability: {pm.status} ({pm.prompt_hash[:16]}...)")
            print(f"  - Tool Contracts: {'9/9 STABLE' if tc_ok else 'UNSTABLE'}")
            print(f"  - Selected Objective: {primary.objective_id if primary else 'NONE'}")
            print(f"  - Hardware Classification: {hw_str}")

        return 0 if all_ok else 1

    return 0


def main() -> int:
    return run_lora_cli()
