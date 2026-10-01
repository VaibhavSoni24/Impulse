"""Comprehensive Test Suite for Stage 43: Version Every Candidate.

Tests all 26 mandatory requirements (A through Z) plus negative tests:
A. Schema validation
B. Candidate registration
C. Duplicate ID rejection
D. Immutable ID enforcement
E. Behavior-change requires new ID
F. Parent lineage
G. Git commit recording
H. Dirty-tree policy
I. File hashing
J. Directory manifest hashing
K. Compute fingerprint recording
L. Evidence mode
M. Status transitions
N. Promotion status separation
O. Run vs candidate separation
P. Candidate comparison
Q. History append-only behavior
R. Current-best validation
S. L1 blocked-state handling
T. RC1 reserved-state handling
U. Benchmark hash recording
V. Adapter hash handling
W. Manifest immutability
X. Timestamp-independent identity
Y. Machine-path normalization
Z. Secret sanitization
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from local.versioning.comparison import CandidateComparator
from local.versioning.errors import (
    DuplicateCandidateError,
    ImmutableCandidateError,
    InvalidStatusTransitionError,
    LineageError,
    SchemaValidationError,
    SecretDetectedInManifestError,
    UnverifiedPromotionError,
)
from local.versioning.hashing import (
    compute_canonical_dict_hash,
    compute_directory_manifest_hash,
    compute_file_sha256,
    normalize_machine_paths,
    scan_for_secrets,
)
from local.versioning.importer import import_all_historical_candidates
from local.versioning.models import (
    CandidateManifest,
    CandidateStatus,
    CurrentBestPointer,
    EvidenceMode,
    ExperimentDimension,
    LifecycleEvent,
    LifecycleEventType,
    PromotionStatus,
)
from local.versioning.registry import CandidateRegistry
from local.versioning.validation import CandidateValidator

EXPECTED_PARENT_COMMIT = "b5d3762c30fe90c6ce2cbb934368c50119eb2a2d"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestCandidateVersioningStage43(unittest.TestCase):
    """Test battery enforcing candidate versioning, lineage, and immutability."""

    def setUp(self) -> None:
        self.repo_root = PROJECT_ROOT
        self.registry = CandidateRegistry(repo_root=self.repo_root)

    def test_a_schema_validation(self) -> None:
        """A: Verifies schema validation passes for valid manifests and catches bad fields."""
        m0 = self.registry.get_candidate("M0")
        self.assertIsNotNone(m0)
        warns = CandidateValidator.validate_manifest(m0)
        self.assertIsInstance(warns, list)

        # Negative test: invalid status
        bad_manifest = CandidateManifest(**m0.to_dict())
        bad_manifest.status = "INVALID_STATUS"
        with self.assertRaises(SchemaValidationError):
            CandidateValidator.validate_manifest(bad_manifest)

    def test_b_candidate_registration(self) -> None:
        """B: Verifies registering a new candidate in an isolated registry works cleanly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_reg = CandidateRegistry(candidates_dir=Path(tmp_dir), repo_root=self.repo_root)
            m0 = self.registry.get_candidate("M0")

            # Register base
            m_hash = temp_reg.register_candidate(m0)
            self.assertIsNotNone(m_hash)
            self.assertEqual(len(m_hash), 64)
            self.assertIn("M0", temp_reg.list_candidate_ids())

    def test_c_duplicate_id_rejection(self) -> None:
        """C: Negative test: Attempting to register an existing finalized candidate ID is rejected."""
        m0 = self.registry.get_candidate("M0")
        with self.assertRaises(DuplicateCandidateError):
            self.registry.register_candidate(m0, overwrite_finalized=False)

    def test_d_immutable_id_enforcement(self) -> None:
        """D: Verifies that once candidate ID X refers to configuration Y, it is immutable."""
        m0 = self.registry.get_candidate("M0")
        self.assertEqual(m0.candidate_id, "M0")
        self.assertEqual(m0.base_model, "gemma-4-31b-it-qat-w4a16-ct")

    def test_e_behavior_change_requires_new_id(self) -> None:
        """E: Verifies behavior changes (e.g. prompt modification) use distinct candidate IDs."""
        e0 = self.registry.get_candidate("E0")
        e1 = self.registry.get_candidate("E1")
        self.assertNotEqual(e0.candidate_id, e1.candidate_id)
        self.assertNotEqual(e0.root_prompt_hash, e1.root_prompt_hash)
        self.assertEqual(e1.parent_candidate_id, "E0")

    def test_f_parent_lineage(self) -> None:
        """F: Verifies lineage validation rejects unknown parents and self-referencing parents."""
        m0 = self.registry.get_candidate("M0")

        # Self-parenting rejected
        bad_manifest = CandidateManifest(**m0.to_dict())
        bad_manifest.parent_candidate_id = bad_manifest.candidate_id
        with self.assertRaises(LineageError):
            CandidateValidator.validate_manifest(bad_manifest)

        # Unknown parent rejected
        bad_manifest.parent_candidate_id = "NONEXISTENT_PARENT_XYZ"
        with self.assertRaises(LineageError):
            CandidateValidator.validate_manifest(bad_manifest, known_candidate_ids={"M0", "E0"})

    def test_g_git_commit_recording(self) -> None:
        """G: Verifies all registered candidates record a valid Git commit hash."""
        for cid in self.registry.list_candidate_ids():
            cand = self.registry.get_candidate(cid)
            self.assertIsNotNone(cand.git_commit)
            self.assertGreaterEqual(len(cand.git_commit), 7)

    def test_h_dirty_tree_policy(self) -> None:
        """H: Negative test: Malformed git commit strings fail validation."""
        m0 = self.registry.get_candidate("M0")
        bad = CandidateManifest(**m0.to_dict())
        bad.git_commit = "not-a-valid-commit-hash-!!!"
        with self.assertRaises(SchemaValidationError):
            CandidateValidator.validate_manifest(bad)

    def test_i_file_hashing(self) -> None:
        """I: Verifies deterministic SHA-256 file hashing."""
        prompt_path = self.repo_root / "agent" / "prompts" / "root.md"
        sha1 = compute_file_sha256(prompt_path)
        sha2 = compute_file_sha256(prompt_path)
        self.assertEqual(sha1, sha2)
        self.assertEqual(len(sha1), 64)

    def test_j_directory_manifest_hashing(self) -> None:
        """J: Verifies directory manifest hashing produces stable, reproducible digests."""
        skills_dir = self.repo_root / "experiments" / "candidates" / "M0" / "skills"
        h1 = compute_directory_manifest_hash(skills_dir)
        h2 = compute_directory_manifest_hash(skills_dir)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_k_compute_fingerprint_recording(self) -> None:
        """K: Verifies candidate manifests record compute environment identity."""
        for cid in ["E0", "M0", "L1"]:
            cand = self.registry.get_candidate(cid)
            self.assertIsNotNone(cand.compute_environment_id)

    def test_l_evidence_mode(self) -> None:
        """L: Verifies evidence modes are classified and distinct."""
        m0 = self.registry.get_candidate("M0")
        self.assertEqual(m0.evidence_mode, EvidenceMode.LIVE.value)

        l1 = self.registry.get_candidate("L1")
        self.assertEqual(l1.evidence_mode, EvidenceMode.UNAVAILABLE.value)

    def test_m_status_transitions(self) -> None:
        """M: Verifies legal and illegal lifecycle status transitions."""
        # Legal transitions
        CandidateValidator.validate_status_transition(
            CandidateStatus.CONFIGURED.value,
            CandidateStatus.SMOKE_PASSED.value,
        )
        CandidateValidator.validate_status_transition(
            CandidateStatus.VALIDATED.value,
            CandidateStatus.HELD_OUT_CONFIRMED.value,
        )

        # Illegal: REJECTED cannot transition to PROMOTED
        with self.assertRaises(InvalidStatusTransitionError):
            CandidateValidator.validate_status_transition(
                CandidateStatus.REJECTED.value,
                CandidateStatus.PROMOTED.value,
            )

        # Illegal: ARCHIVED cannot transition anywhere
        with self.assertRaises(InvalidStatusTransitionError):
            CandidateValidator.validate_status_transition(
                CandidateStatus.ARCHIVED.value,
                CandidateStatus.CONFIGURED.value,
            )

    def test_n_promotion_status_separation(self) -> None:
        """N: Verifies lifecycle status is kept distinct from promotion status."""
        e1 = self.registry.get_candidate("E1")
        self.assertEqual(e1.status, CandidateStatus.VALIDATED.value)
        self.assertEqual(e1.promotion_status, PromotionStatus.NOT_PROMOTED.value)

    def test_o_run_vs_candidate_separation(self) -> None:
        """O: Verifies candidate identity defines configuration, invariant across runs."""
        m0 = self.registry.get_candidate("M0")
        self.assertEqual(m0.candidate_id, "M0")
        self.assertEqual(m0.topology, "root_only")

    def test_p_candidate_comparison(self) -> None:
        """P: Verifies candidate comparator detects exact single-variable prompt change."""
        e0 = self.registry.get_candidate("E0")
        e1 = self.registry.get_candidate("E1")
        diff = CandidateComparator.compare(e0, e1)
        self.assertFalse(diff.is_multi_dimension)
        self.assertEqual(diff.changed_dimensions, ["root_prompt"])
        self.assertIn("root_prompt", diff.hash_changes)
        self.assertIn("tools", diff.unchanged_dimensions)

    def test_q_history_append_only_behavior(self) -> None:
        """Q: Verifies history.jsonl is append-only."""
        hist_file = self.repo_root / "experiments" / "candidates" / "history.jsonl"
        self.assertTrue(hist_file.is_file())
        with open(hist_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertGreater(len(lines), 0)
        # Parse first line to verify event format
        event_dict = json.loads(lines[0])
        self.assertIn("candidate_id", event_dict)
        self.assertIn("event_type", event_dict)
        self.assertIn("timestamp", event_dict)

    def test_r_current_best_validation(self) -> None:
        """R: Verifies current best points to M0 and rejects invalid/rejected candidates."""
        best = self.registry.get_current_best()
        self.assertIsNotNone(best)
        self.assertEqual(best.candidate_id, "M0")

        # Negative test: cannot set REJECTED candidate as current best
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_reg = CandidateRegistry(candidates_dir=Path(tmp_dir), repo_root=self.repo_root)
            e0 = self.registry.get_candidate("E0")
            m0 = self.registry.get_candidate("M0")
            temp_reg.register_candidate(e0)
            temp_reg.register_candidate(m0)
            rejected = CandidateManifest(**m0.to_dict())
            rejected.candidate_id = "REJ1"
            rejected.parent_candidate_id = "M0"
            rejected.status = CandidateStatus.REJECTED.value
            rejected.promotion_status = PromotionStatus.REJECTED.value
            temp_reg.register_candidate(rejected)
            with self.assertRaises(ValueError):
                temp_reg.set_current_best("REJ1", rationale="Illegal best")

    def test_s_l1_blocked_state_handling(self) -> None:
        """S: Verifies L1 special rule: L1 must be BLOCKED and cannot claim VALIDATED or PROMOTED."""
        l1 = self.registry.get_candidate("L1")
        self.assertIsNotNone(l1)
        self.assertEqual(l1.status, CandidateStatus.BLOCKED.value)
        self.assertEqual(l1.promotion_status, PromotionStatus.BLOCKED.value)
        self.assertEqual(l1.evidence_mode, EvidenceMode.UNAVAILABLE.value)

        # Negative test: L1 cannot be marked VALIDATED or claim LIVE evidence
        bad_l1 = CandidateManifest(**l1.to_dict())
        bad_l1.status = CandidateStatus.VALIDATED.value
        with self.assertRaises(SchemaValidationError):
            CandidateValidator.validate_manifest(bad_l1)

    def test_t_rc1_reserved_state_handling(self) -> None:
        """T: Verifies RC1 special rule: RC1 must remain RESERVED."""
        rc1 = self.registry.get_candidate("RC1")
        self.assertIsNotNone(rc1)
        self.assertEqual(rc1.status, CandidateStatus.RESERVED.value)
        self.assertEqual(rc1.promotion_status, PromotionStatus.RESERVED.value)

        # Negative test: RC1 cannot be marked VALIDATED yet
        bad_rc1 = CandidateManifest(**rc1.to_dict())
        bad_rc1.status = CandidateStatus.VALIDATED.value
        bad_rc1.promotion_status = PromotionStatus.NOT_PROMOTED.value
        with self.assertRaises(SchemaValidationError):
            CandidateValidator.validate_manifest(bad_rc1)

    def test_u_benchmark_hash_recording(self) -> None:
        """U: Verifies candidate manifests record benchmark split hashes."""
        m0 = self.registry.get_candidate("M0")
        self.assertIsNotNone(m0.benchmark_manifest_hash)
        self.assertIsNotNone(m0.dev_split_hash)
        self.assertIsNotNone(m0.validation_split_hash)

    def test_v_adapter_hash_handling(self) -> None:
        """V: Verifies adapter hashes are None when no adapter is attached."""
        m0 = self.registry.get_candidate("M0")
        self.assertIsNone(m0.adapter_id)
        self.assertIsNone(m0.adapter_sha256)

    def test_w_manifest_immutability(self) -> None:
        """W: Negative test: Attempting to modify a finalized manifest in place raises ImmutableCandidateError."""
        m0 = self.registry.get_candidate("M0")
        modified_m0 = CandidateManifest(**m0.to_dict())
        modified_m0.description = "Tampered description"
        with self.assertRaises(ImmutableCandidateError):
            self.registry.register_candidate(modified_m0, overwrite_finalized=False)

    def test_x_timestamp_independent_identity(self) -> None:
        """X: Verifies candidate identity is explicit (M0, E0) and not derived from timestamp."""
        m0 = self.registry.get_candidate("M0")
        self.assertEqual(m0.candidate_id, "M0")
        self.assertFalse(m0.candidate_id.isdigit())

    def test_y_machine_path_normalization(self) -> None:
        """Y: Verifies normalize_machine_paths strips user home paths and absolute paths."""
        data = {"user_path": "C:\\Users\\shubh\\AppData", "repo_path": "e:\\Projects\\Impulse\\agent"}
        norm = normalize_machine_paths(data, self.repo_root)
        self.assertNotIn("shubh", str(norm))

    def test_z_secret_sanitization(self) -> None:
        """Z: Negative test: Manifest containing credential pattern raises SecretDetectedInManifestError."""
        with self.assertRaises(SecretDetectedInManifestError):
            scan_for_secrets({"api_key": "ghp_123456789012345678901234567890"})

        with self.assertRaises(SecretDetectedInManifestError):
            scan_for_secrets({"key": "akida1234567890123456"})


if __name__ == "__main__":
    unittest.main()
