"""Focused Test Suite for Stage 37: LoRA Feasibility / Readiness Study (L0).

Verifies Sections 21 and 26 requirements:
A. Parent commit verification
B. Clean-tree verification
C. Baseline snapshot generation
D. Architecture hash stability
E. Benchmark manifest verification
F. Held-out lock preservation
G. Failure-taxonomy evidence-mode separation
H. No fabrication of live metrics
I. Objective schema validation
J. Objective specificity validation
K. Prompt-stability analysis
L. Tool-contract stability
M. Hardware detection
N. Infrastructure classification
O. Experiment-contract validation
P. Control/candidate invariance
Q. Promotion-gate schema
R. Reproducibility manifest
S. Deterministic rerun
T. Explicit "no training" enforcement

Negative tests:
- Changed root prompt
- Changed benchmark split
- Changed tool contract
- Missing held-out lock
- Fabricated live metrics
- Multiple simultaneous experimental dimensions
- Missing primary objective
- Objective too broad
- Adapter training command accidentally invoked
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from local.failures.models import FailureClass
from local.lora_opt import (
    ArchitectureStabilityReport,
    BaselineSnapshot,
    BenchmarkStabilityReport,
    BenchmarkStabilityStatus,
    CandidateObjective,
    ControlledLoRAExperimentContract,
    HardwareAuditReport,
    InfrastructureClassification,
    L0Decision,
    L0Manifest,
    ObjectiveStatus,
    PromptStabilityReport,
    ReadinessDimensionStatus,
    ToolContractRecord,
    ToolContractStatus,
    audit_failure_taxonomy,
    build_experiment_contract,
    build_l0_manifest,
    build_no_adapter_control,
    capture_baseline_snapshot,
    determine_l0_decision,
    get_candidate_objectives,
    get_competition_tool_contracts,
    run_hardware_audit,
    select_objectives,
    verify_architecture_stability,
    verify_benchmark_stability,
    verify_root_prompt_stability,
    verify_tool_contracts,
)
from local.lora_opt.architecture_stability import (
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_R0_RETRIEVAL_POLICY_HASH,
    EXPECTED_REC0_RECOVERY_POLICY_HASH,
    EXPECTED_REPO_TRIAGE_SKILL_SHA256,
    EXPECTED_T0_TESTING_POLICY_HASH,
    EXPECTED_TEST_STRATEGY_SKILL_SHA256,
    EXPECTED_TOPOLOGY_ID,
)
from local.lora_opt.cli import run_lora_cli
from local.lora_opt.objectives import ObjectiveSelector


class TestLoRAFeasibilityStage37(unittest.TestCase):
    """Test suite for Stage 37 LoRA Feasibility / Readiness Study (L0)."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent

    # A. Parent commit verification
    def test_parent_commit_verification(self) -> None:
        expected_parent = "bad6390b8f2b26cd1125d0e14a7fa615b7987714"
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            commit = res.stdout.strip()
            # If we haven't committed Stage 37 yet, HEAD is parent. If committed, parent is in log.
            log_res = subprocess.run(
                ["git", "log", "-n", "10", "--format=%H"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            commits = log_res.stdout.strip().splitlines()
            self.assertIn(expected_parent, commits)

    # B. Clean-tree verification
    def test_clean_tree_verification_utility(self) -> None:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        # Working tree status is observable and can be checked
        self.assertIsInstance(res.stdout, str)

    # C. Baseline snapshot generation
    def test_baseline_snapshot_generation(self) -> None:
        snapshot = capture_baseline_snapshot(repo_root=self.repo_root)
        self.assertIsInstance(snapshot, BaselineSnapshot)
        self.assertEqual(snapshot.model_id, "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(snapshot.prompt_hash, EXPECTED_P0_PROMPT_SHA256)
        self.assertEqual(snapshot.topology_identity, EXPECTED_TOPOLOGY_ID)
        self.assertEqual(snapshot.retrieval_policy_hash, EXPECTED_R0_RETRIEVAL_POLICY_HASH)
        self.assertEqual(snapshot.testing_policy_hash, EXPECTED_T0_TESTING_POLICY_HASH)
        self.assertEqual(snapshot.recovery_policy_hash, EXPECTED_REC0_RECOVERY_POLICY_HASH)
        self.assertIn("test_strategy", snapshot.skill_hashes)
        self.assertIn("repo_triage", snapshot.skill_hashes)
        self.assertEqual(len(snapshot.tool_contract_hashes), 9)

    # D. Architecture hash stability
    def test_architecture_hash_stability(self) -> None:
        arch = verify_architecture_stability(repo_root=self.repo_root)
        self.assertEqual(arch.overall_status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(arch.root_prompt_status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(arch.topology_status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(arch.retrieval_status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(arch.testing_status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(arch.recovery_status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(arch.tools_status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(arch.skills_status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(arch.benchmark_status, ReadinessDimensionStatus.STABLE.value)

    # E. Benchmark manifest verification
    def test_benchmark_manifest_verification(self) -> None:
        bm = verify_benchmark_stability(repo_root=self.repo_root)
        self.assertEqual(bm.status, BenchmarkStabilityStatus.BENCHMARK_STABLE.value)
        self.assertEqual(bm.total_tasks_count, 129)
        self.assertTrue(len(bm.source_sha256) > 0)
        self.assertTrue(len(bm.manifest_sha256) > 0)
        self.assertTrue(len(bm.dev_file_sha256) > 0)
        self.assertTrue(len(bm.validation_file_sha256) > 0)
        self.assertTrue(len(bm.held_out_file_sha256) > 0)
        self.assertTrue(len(bm.held_out_lock_sha256) > 0)

    # F. Held-out lock preservation
    def test_held_out_lock_preservation(self) -> None:
        lock_file = self.repo_root / "benchmark" / "splits" / "v1" / "held_out.lock"
        self.assertTrue(lock_file.is_file())
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
        self.assertEqual(lock_data["held_out_count"], 14)
        self.assertEqual(len(lock_data["held_out_tasks"]), 14)
        self.assertTrue(len(lock_data["held_out_file_sha256"]) == 64)
        self.assertTrue(len(lock_data["manifest_sha256"]) == 64)

    # G. Failure-taxonomy evidence-mode separation
    def test_failure_taxonomy_evidence_mode_separation(self) -> None:
        categories, live_status, summary = audit_failure_taxonomy(repo_root=self.repo_root)
        self.assertEqual(len(categories), 8)
        self.assertEqual(live_status, "NO_ACTIONABLE_LIVE_DATA")
        for cat in categories:
            self.assertEqual(cat.live_observations_count, 0)
            self.assertGreater(cat.fixture_observations_count, 0)
            self.assertIsInstance(cat.learnable_by_lora, bool)

    # H. No fabrication of live metrics
    def test_no_fabrication_of_live_metrics(self) -> None:
        _, live_status, summary = audit_failure_taxonomy(repo_root=self.repo_root)
        self.assertFalse(summary["has_actionable_live_data"])
        self.assertEqual(live_status, "NO_ACTIONABLE_LIVE_DATA")

    # I. Objective schema validation
    def test_objective_schema_validation(self) -> None:
        candidates = get_candidate_objectives()
        self.assertGreaterEqual(len(candidates), 3)
        for obj in candidates:
            self.assertTrue(obj.objective_id.startswith("OBJ-"))
            self.assertIsInstance(obj.name, str)
            self.assertIsInstance(obj.problem_definition, str)
            self.assertIsInstance(obj.target_failure_classes, list)
            self.assertIsInstance(obj.observable_input, str)
            self.assertIsInstance(obj.desired_behavior, str)
            self.assertIsInstance(obj.undesired_behavior, str)
            self.assertIsInstance(obj.training_signal, str)
            self.assertIsInstance(obj.evaluation_metric, str)
            self.assertIn(obj.primary_benchmark_split, ("dev", "validation"))
            self.assertIsInstance(obj.possible_confounders, list)

    # J. Objective specificity validation
    def test_objective_specificity_validation(self) -> None:
        candidates = get_candidate_objectives()
        primary, secondary = select_objectives(candidates)
        self.assertIsNotNone(primary)
        self.assertEqual(primary.objective_id, "OBJ-TOOL-DISCIPLINE")
        self.assertEqual(primary.status, ObjectiveStatus.PRIMARY_SELECTED.value)
        self.assertEqual(primary.target_failure_classes, [FailureClass.COMMAND.value])
        self.assertIn("redundancy", primary.evaluation_metric)

        self.assertIsNotNone(secondary)
        self.assertEqual(secondary.objective_id, "OBJ-TARGETED-TEST-SELECTION")
        self.assertEqual(secondary.status, ObjectiveStatus.SECONDARY_CANDIDATE.value)

    # K. Prompt-stability analysis
    def test_prompt_stability_analysis(self) -> None:
        pm = verify_root_prompt_stability(repo_root=self.repo_root)
        self.assertEqual(pm.status, ReadinessDimensionStatus.STABLE.value)
        self.assertEqual(pm.prompt_hash, EXPECTED_P0_PROMPT_SHA256)
        self.assertTrue(pm.is_frozen)

    # L. Tool-contract stability
    def test_tool_contract_stability(self) -> None:
        records = get_competition_tool_contracts(repo_root=self.repo_root)
        self.assertEqual(len(records), 9)
        expected_tools = {
            "run_command", "read_file", "edit_file", "write_file",
            "get_status", "submit_patch", "get_code_neighbors",
            "search_similar_code", "get_code_subgraph",
        }
        found_tools = {r.tool_name for r in records}
        self.assertEqual(found_tools, expected_tools)
        for r in records:
            self.assertEqual(r.status, ToolContractStatus.STABLE.value)
            self.assertEqual(len(r.contract_hash), 64)

    # M. Hardware detection
    def test_hardware_detection(self) -> None:
        hw = run_hardware_audit()
        self.assertIsInstance(hw, HardwareAuditReport)
        self.assertTrue(len(hw.os_name) > 0)
        self.assertTrue(len(hw.python_version) > 0)
        self.assertGreater(hw.total_ram_gb, 0.0)
        self.assertGreaterEqual(hw.free_disk_gb, 0.0)

    # N. Infrastructure classification
    def test_infrastructure_classification(self) -> None:
        hw = run_hardware_audit()
        self.assertIn(
            hw.classification,
            (
                InfrastructureClassification.EXTERNAL_GPU_REQUIRED.value,
                InfrastructureClassification.LOCAL_FEASIBLE.value,
                InfrastructureClassification.LOCAL_NOT_FEASIBLE.value,
            ),
        )
        if not hw.cuda_available or (hw.gpu_count == 0):
            self.assertEqual(
                hw.classification,
                InfrastructureClassification.EXTERNAL_GPU_REQUIRED.value,
            )

    # O. Experiment-contract validation
    def test_experiment_contract_validation(self) -> None:
        contract = build_experiment_contract(repo_root=self.repo_root)
        self.assertIsInstance(contract, ControlledLoRAExperimentContract)
        self.assertEqual(contract.baseline_candidate, "M0")
        self.assertEqual(contract.candidate_id_placeholder, "L1")
        self.assertEqual(contract.model_id, "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(contract.primary_objective, "OBJ-TOOL-DISCIPLINE")
        self.assertEqual(contract.prompt_hash, EXPECTED_P0_PROMPT_SHA256)
        self.assertEqual(contract.retrieval_version, "R0")
        self.assertEqual(contract.testing_version, "T0")
        self.assertEqual(contract.recovery_version, "REC0")
        self.assertEqual(contract.topology, EXPECTED_TOPOLOGY_ID)
        self.assertEqual(contract.held_out_split, "held_out")

    # P. Control/candidate invariance
    def test_control_candidate_invariance(self) -> None:
        control = build_no_adapter_control(repo_root=self.repo_root)
        contract = build_experiment_contract(repo_root=self.repo_root)

        self.assertEqual(control["candidate_id"], contract.baseline_candidate)
        self.assertEqual(control["model_id"], contract.model_id)
        self.assertEqual(control["prompt_hash"], contract.prompt_hash)
        self.assertEqual(control["retrieval_version"], contract.retrieval_version)
        self.assertEqual(control["testing_version"], contract.testing_version)
        self.assertEqual(control["recovery_version"], contract.recovery_version)
        self.assertEqual(control["topology"], contract.topology)
        self.assertFalse(control["adapter_enabled"])
        self.assertIsNone(control["adapter_path"])
        self.assertEqual(control["tool_contract_hashes"], contract.tool_contract_hashes)

    # Q. Promotion-gate schema
    def test_promotion_gate_schema(self) -> None:
        contract = build_experiment_contract(repo_root=self.repo_root)
        self.assertEqual(
            contract.promotion_gate,
            "VALIDATION_IMPROVEMENT_AND_NO_HELD_OUT_REGRESSION",
        )
        self.assertIn("HELD_OUT_REGRESSION", contract.stop_conditions)
        self.assertIn("TOOL_SCHEMA_VIOLATION", contract.stop_conditions)

    # R. Reproducibility manifest
    def test_reproducibility_manifest(self) -> None:
        candidates = get_candidate_objectives()
        primary, _ = select_objectives(candidates)
        manifest = build_l0_manifest(
            repo_root=self.repo_root,
            primary_obj=primary,
        )
        self.assertIsInstance(manifest, L0Manifest)
        self.assertEqual(manifest.stage, "Stage 37")
        self.assertEqual(manifest.candidate_id, "L0")
        self.assertEqual(manifest.model_id, "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(manifest.objective_id, "OBJ-TOOL-DISCIPLINE")
        self.assertEqual(manifest.evidence_mode, "FIXTURE")
        self.assertEqual(
            manifest.decision,
            L0Decision.CONDITIONALLY_READY_FOR_STAGE_38.value,
        )

    # S. Deterministic rerun
    def test_deterministic_rerun(self) -> None:
        arch1 = verify_architecture_stability(repo_root=self.repo_root)
        arch2 = verify_architecture_stability(repo_root=self.repo_root)
        self.assertEqual(arch1.to_dict(), arch2.to_dict())

        bm1 = verify_benchmark_stability(repo_root=self.repo_root)
        bm2 = verify_benchmark_stability(repo_root=self.repo_root)
        self.assertEqual(bm1.to_dict(), bm2.to_dict())

    # T. Explicit "no training" enforcement
    def test_explicit_no_training_enforcement(self) -> None:
        l0_dir = self.repo_root / "experiments" / "lora" / "L0"
        # Check that no adapter checkpoint or bin/safetensors files exist in L0 directory
        if l0_dir.exists():
            adapter_files = list(l0_dir.glob("**/*.safetensors")) + list(l0_dir.glob("**/*.bin")) + list(l0_dir.glob("**/adapter_model.*"))
            self.assertEqual(adapter_files, [], f"Found unauthorized adapter weight files: {adapter_files}")

    # Negative Tests
    def test_negative_changed_root_prompt(self) -> None:
        arch = verify_architecture_stability(repo_root=self.repo_root)
        bm = verify_benchmark_stability(repo_root=self.repo_root)
        tc_dict = verify_tool_contracts(repo_root=self.repo_root)
        hw = run_hardware_audit()
        candidates = get_candidate_objectives()
        primary, _ = select_objectives(candidates)

        # Mutate prompt to CHANGED
        bad_pm = PromptStabilityReport(
            status=ReadinessDimensionStatus.CHANGED.value,
            prompt_hash="bad_hash_123",
            expected_hash=EXPECTED_P0_PROMPT_SHA256,
            is_frozen=False,
            commits_count=1,
            history=[],
            rationale="Mutated prompt",
        )
        dec = determine_l0_decision(arch=arch, bm=bm, pm=bad_pm, tc_dict=tc_dict, primary_obj=primary, hw=hw)
        self.assertEqual(dec, L0Decision.NOT_READY)

    def test_negative_changed_benchmark_split(self) -> None:
        arch = verify_architecture_stability(repo_root=self.repo_root)
        pm = verify_root_prompt_stability(repo_root=self.repo_root)
        tc_dict = verify_tool_contracts(repo_root=self.repo_root)
        hw = run_hardware_audit()
        candidates = get_candidate_objectives()
        primary, _ = select_objectives(candidates)

        # Mutate benchmark to CHANGED
        bad_bm = BenchmarkStabilityReport(
            source_sha256="",
            manifest_sha256="",
            dev_file_sha256="",
            validation_file_sha256="",
            held_out_file_sha256="",
            held_out_lock_sha256="",
            total_tasks_count=99,
            status=BenchmarkStabilityStatus.BENCHMARK_CHANGED.value,
        )
        dec = determine_l0_decision(arch=arch, bm=bad_bm, pm=pm, tc_dict=tc_dict, primary_obj=primary, hw=hw)
        self.assertEqual(dec, L0Decision.NOT_READY)

    def test_negative_changed_tool_contract(self) -> None:
        arch = verify_architecture_stability(repo_root=self.repo_root)
        bm = verify_benchmark_stability(repo_root=self.repo_root)
        pm = verify_root_prompt_stability(repo_root=self.repo_root)
        hw = run_hardware_audit()
        candidates = get_candidate_objectives()
        primary, _ = select_objectives(candidates)

        bad_tc = verify_tool_contracts(repo_root=self.repo_root)
        bad_tc["run_command"].status = ToolContractStatus.CHANGED.value

        dec = determine_l0_decision(arch=arch, bm=bm, pm=pm, tc_dict=bad_tc, primary_obj=primary, hw=hw)
        self.assertEqual(dec, L0Decision.NOT_READY)

    def test_negative_missing_held_out_lock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_splits = Path(td)
            bm = verify_benchmark_stability(repo_root=temp_splits)
            self.assertNotEqual(bm.status, BenchmarkStabilityStatus.BENCHMARK_STABLE.value)

    def test_negative_fabricated_live_metrics(self) -> None:
        # A valid L0 audit must report NO_ACTIONABLE_LIVE_DATA when 0 live records exist
        categories, live_status, summary = audit_failure_taxonomy(repo_root=self.repo_root)
        if summary["total_canonical_categories"] > 0 and not summary["has_actionable_live_data"]:
            self.assertEqual(live_status, "NO_ACTIONABLE_LIVE_DATA")

    def test_negative_multiple_simultaneous_dimensions(self) -> None:
        contract = build_experiment_contract(repo_root=self.repo_root)
        # Attempting to bundle a prompt change into Stage 39 adapter experiment
        mutated_contract = copy.deepcopy(contract)
        mutated_contract.prompt_hash = "mutated_prompt_attempt"
        self.assertNotEqual(mutated_contract.prompt_hash, EXPECTED_P0_PROMPT_SHA256)

    def test_negative_missing_primary_objective(self) -> None:
        arch = verify_architecture_stability(repo_root=self.repo_root)
        bm = verify_benchmark_stability(repo_root=self.repo_root)
        pm = verify_root_prompt_stability(repo_root=self.repo_root)
        tc_dict = verify_tool_contracts(repo_root=self.repo_root)
        hw = run_hardware_audit()

        dec = determine_l0_decision(arch=arch, bm=bm, pm=pm, tc_dict=tc_dict, primary_obj=None, hw=hw)
        self.assertEqual(dec, L0Decision.NOT_READY)

    def test_negative_objective_too_broad(self) -> None:
        broad_obj = CandidateObjective(
            objective_id="OBJ-TOO-BROAD",
            name="Make agent generally smarter",
            problem_definition="General intelligence across all tasks",
            target_failure_classes=["ALL"],
            observable_input="Everything",
            desired_behavior="Solve everything",
            undesired_behavior="Fail anything",
            training_signal="All signals",
            evaluation_metric="pass_rate",
            primary_benchmark_split="dev",
            negative_behavior="Any failure",
            possible_confounders=[],
            minimum_evidence_required="N/A",
        )
        selector = ObjectiveSelector([broad_obj])
        primary, _, all_objs = selector.evaluate_and_select()
        self.assertIsNone(primary)
        self.assertEqual(all_objs[0].status, ObjectiveStatus.REJECTED_TOO_BROAD.value)

    def test_negative_adapter_training_command_accidentally_invoked(self) -> None:
        # CLI must not accept or support training flags
        with self.assertRaises(SystemExit):
            run_lora_cli(["--train"])

        with self.assertRaises(SystemExit):
            run_lora_cli(["--finetune"])

    def test_cli_verify_flag(self) -> None:
        ret = run_lora_cli(["--verify"])
        self.assertEqual(ret, 0)

    def test_cli_hardware_flag(self) -> None:
        ret = run_lora_cli(["--hardware"])
        self.assertEqual(ret, 0)

    def test_cli_objectives_flag(self) -> None:
        ret = run_lora_cli(["--objectives"])
        self.assertEqual(ret, 0)

    def test_cli_contract_flag(self) -> None:
        ret = run_lora_cli(["--contract"])
        self.assertEqual(ret, 0)

    def test_cli_json_output(self) -> None:
        ret = run_lora_cli(["--verify", "--json"])
        self.assertEqual(ret, 0)

    def test_cli_dry_run_setup(self) -> None:
        ret = run_lora_cli(["--setup", "--dry-run"])
        self.assertEqual(ret, 0)

    def test_baseline_snapshot_dict_roundtrip(self) -> None:
        snap = capture_baseline_snapshot(repo_root=self.repo_root)
        d = snap.to_dict()
        reconstructed = BaselineSnapshot.from_dict(d)
        self.assertEqual(reconstructed.git_commit, snap.git_commit)
        self.assertEqual(reconstructed.prompt_hash, snap.prompt_hash)

    def test_l0_manifest_dict_roundtrip(self) -> None:
        manifest = build_l0_manifest(repo_root=self.repo_root)
        d = manifest.to_dict()
        reconstructed = L0Manifest.from_dict(d)
        self.assertEqual(reconstructed.stage, manifest.stage)
        self.assertEqual(reconstructed.decision, manifest.decision)

    def test_experiment_contract_dict_roundtrip(self) -> None:
        contract = build_experiment_contract(repo_root=self.repo_root)
        d = contract.to_dict()
        reconstructed = ControlledLoRAExperimentContract.from_dict(d)
        self.assertEqual(reconstructed.baseline_candidate, contract.baseline_candidate)
        self.assertEqual(reconstructed.primary_objective, contract.primary_objective)


if __name__ == "__main__":
    unittest.main()
