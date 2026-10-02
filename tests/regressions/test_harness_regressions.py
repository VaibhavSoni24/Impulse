"""Unittest discovery adapter for IMPULSE Failure Regression Suite (Stage 45 Phase 4).

Enables native unittest discovery via:
    python -m unittest discover tests/regressions

Directly delegates execution to the authoritative RegressionRunner to prevent duplicate logic.
"""

from __future__ import annotations

import unittest

from local.regressions.models import RegressionResultStatus
from local.regressions.runner import RegressionRunner


class TestHarnessRegressions(unittest.TestCase):
    """Executes registered regression cases within unittest runner."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = RegressionRunner()

    def test_reg_retrieval_001_weak_semantic(self) -> None:
        res = self.runner.run_by_id("REG-RETRIEVAL-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_retrieval_002_budget_exhaustion(self) -> None:
        res = self.runner.run_by_id("REG-RETRIEVAL-002")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_policy_001_edit_before_recon(self) -> None:
        res = self.runner.run_by_id("REG-POLICY-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_001_repeated_command(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_002_repeated_error(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-002")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_003_repeated_edit(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-003")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_004_repeated_hypothesis(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-004")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_005_recovery_loop(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-005")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_006_recovery_thrashing(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-006")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_007_retry_waste(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-007")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_008_recovery_omission(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-008")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_009_late_recovery(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-009")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_recovery_010_failed_recovery(self) -> None:
        res = self.runner.run_by_id("REG-RECOVERY-010")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_hygiene_001_temporary_file(self) -> None:
        res = self.runner.run_by_id("REG-HYGIENE-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_diff_001_unrelated_file(self) -> None:
        res = self.runner.run_by_id("REG-DIFF-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_graph_001_caller_inspection(self) -> None:
        res = self.runner.run_by_id("REG-GRAPH-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_testing_001_stop_after_first_red_test(self) -> None:
        res = self.runner.run_by_id("REG-TESTING-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_testing_002_unconstrained_repo_sweep(self) -> None:
        res = self.runner.run_by_id("REG-TESTING-002")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_submission_001_submit_without_final_diff(self) -> None:
        res = self.runner.run_by_id("REG-SUBMISSION-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_benchmark_001_held_out_protection(self) -> None:
        res = self.runner.run_by_id("REG-BENCHMARK-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_reg_blocked_001_long_context_honestly_blocked(self) -> None:
        res = self.runner.run_by_id("REG-BLOCKED-001")
        # Must be honestly BLOCKED, NEVER fake PASS!
        self.assertEqual(res.status, RegressionResultStatus.BLOCKED)
        self.assertIn("BLOCKED", res.actual_result)

    def test_reg_blocked_002_kaggle_isolation_honestly_blocked(self) -> None:
        res = self.runner.run_by_id("REG-BLOCKED-002")
        # Must be honestly BLOCKED, NEVER fake PASS!
        self.assertEqual(res.status, RegressionResultStatus.BLOCKED)
        self.assertIn("BLOCKED", res.actual_result)


if __name__ == "__main__":
    unittest.main()
