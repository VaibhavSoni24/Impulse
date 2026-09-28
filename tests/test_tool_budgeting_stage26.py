"""Focused unit, safety, and regression tests for Tool-Call Budgeting (Stage 26).

Covers:
A. Event model and argument normalization
B. Call count distribution and repetition metrics
C. Information-value metrics and evidence novelty
D. Success contribution analysis (strictly non-causal)
E. Wasteful call detection and classification
F. Bounded tool cache correctness and targeted invalidation
G. Cache bounds and LRU eviction
H. Stage 25 integration (fingerprints, file tracking)
I. E9/E10/E11 regression preservation
J. Security and credential scrubbing
K. Stage 24 invariance verification
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

from local.budgeting import (
    BoundedToolCache,
    EvidenceHistoryTracker,
    EvidenceNovelty,
    InformationValue,
    SAFE_CACHEABLE_TOOLS,
    ToolAssociation,
    ToolBudgetAnalyzer,
    ToolCallCategory,
    ToolCallEvent,
    WasteClassification,
    WasteDetector,
    classify_tool_category,
    compute_arguments_digest,
    normalize_arguments,
    normalize_command,
)
from local.context_compaction import (
    ChangedFileTracker,
    compute_content_sha256,
    compute_file_fingerprint,
    normalize_path,
    sanitize_text,
)
from local.failures import FailureClass, FailureClassifierV1
from local.progress import NoProgressDetectorV1, NoProgressReason, ProgressStatus
from local.recovery import (
    RecoveryActionType,
    RecoveryContext,
    RecoveryControllerV1,
    RecoveryPath,
)
from tests.fixtures.budget_fixtures import (
    FIXTURE_CMD_WITH_SECRET,
    FIXTURE_GRAPH_RELATIONS_1,
    FIXTURE_GRAPH_SEED,
    FIXTURE_GRAPH_SYMBOLS_1,
    FIXTURE_GRAPH_SYMBOLS_2,
    FIXTURE_GRAPH_SYMBOLS_NEW,
    FIXTURE_PATH_NORMALIZED,
    FIXTURE_PATH_WINDOWS,
    FIXTURE_READ_CONTENT_V1,
    FIXTURE_READ_CONTENT_V2,
    FIXTURE_READ_PATH,
    FIXTURE_SEARCH_CANDIDATES_1,
    FIXTURE_SEARCH_CANDIDATES_2,
    FIXTURE_SEARCH_CANDIDATES_NEW,
    FIXTURE_SEARCH_QUERY,
    FIXTURE_STATUS_OUTPUT_1,
    FIXTURE_STATUS_OUTPUT_2,
    FIXTURE_TEST_CMD,
    FIXTURE_TEST_ERROR_SIG,
    FIXTURE_TEST_EXIT_CODE_FAIL,
    FIXTURE_TEST_EXIT_CODE_PASS,
    FIXTURE_TEST_FAILING_TESTS,
    FIXTURE_TEST_PASS_SIG,
    FIXTURE_TEST_PASSING_TESTS,
    FIXTURE_UNRELATED_CONTENT,
    FIXTURE_UNRELATED_PATH,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Specialist Hashes
FROZEN_SCOUT_YAML_SHA256 = "335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877"
FROZEN_SCOUT_PROMPT_SHA256 = "d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805"
FROZEN_DEBUGGER_YAML_SHA256 = "07b936c8abf06d8710138e2ba94611c57e48cd476c0fb945f7c187abd25d9199"
FROZEN_DEBUGGER_PROMPT_SHA256 = "a743a30bcc297fcc1335b34ef5851533ca751a4699e6b0d6aede76510f57082f"
FROZEN_REVIEWER_YAML_SHA256 = "facfcbb4fbc8d42a82f32a6979bf8b090de5857ba92b4641e4a45617b340200c"
FROZEN_REVIEWER_PROMPT_SHA256 = "d2432da56d07170989edbd83add7fe51323df1db6dd458b80f0d893cdb9264c6"
FROZEN_TOPOLOGY_SHARED_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"


def sha256_file(path: Path) -> str:
    """Computes SHA-256 for a given file path."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestToolCallBudgetingStage26(unittest.TestCase):
    """Stage 26 test suite verifying tool-call budgeting, novelty, waste detection, and caching."""

    # =========================================================================
    # A. Event Model and Argument Normalization
    # =========================================================================

    def test_argument_normalization_paths_and_whitespace(self) -> None:
        """Paths are normalized to POSIX slashes and whitespace is collapsed deterministically."""
        raw_args = {"path": "src\\core\\parser.py", "start_line": 10, "end_line": 20}
        norm = normalize_arguments("read_file", raw_args)

        self.assertEqual(norm["path"], "src/core/parser.py")
        self.assertEqual(norm["start_line"], 10)
        self.assertEqual(norm["end_line"], 20)

    def test_command_normalization_preserves_flags_and_targets(self) -> None:
        """Command normalization strips redundant whitespace while preserving critical flags."""
        raw_cmd = "   pytest   -v   --tb=short   tests/test_parser.py   "
        norm_cmd = normalize_command(raw_cmd)
        self.assertEqual(norm_cmd, "pytest -v --tb=short tests/test_parser.py")

    def test_arguments_digest_deterministic(self) -> None:
        """Equivalent arguments produce identical digest regardless of dictionary key insertion order."""
        args1 = {"path": "src/parser.py", "start": 1, "end": 50}
        args2 = {"end": 50, "start": 1, "path": "src/parser.py"}

        norm1 = normalize_arguments("read_file", args1)
        norm2 = normalize_arguments("read_file", args2)

        d1 = compute_arguments_digest("read_file", norm1)
        d2 = compute_arguments_digest("read_file", norm2)
        self.assertEqual(d1, d2)

    # =========================================================================
    # B. Call Count Distribution and Repetition Metrics
    # =========================================================================

    def test_analyzer_distribution_metrics(self) -> None:
        """Analyzer aggregates total calls, distinct calls, and repeated ratios accurately."""
        analyzer = ToolBudgetAnalyzer()

        # Record 3 calls: 2 identical reads and 1 test command
        ev1 = ToolCallEvent(
            run_id="run_1",
            task_id="task_1",
            turn_id=1,
            call_id="call_1",
            tool_name="read_file",
            category=ToolCallCategory.READ_OBSERVATION,
            normalized_arguments={"path": "src/parser.py"},
            repository_state_id="state_v1",
        )
        ev2 = ToolCallEvent(
            run_id="run_1",
            task_id="task_1",
            turn_id=2,
            call_id="call_2",
            tool_name="read_file",
            category=ToolCallCategory.READ_OBSERVATION,
            normalized_arguments={"path": "src/parser.py"},
            repository_state_id="state_v1",
            cache_hit=True,
            waste_class=WasteClassification.SAFE_REDUNDANT,
        )
        ev3 = ToolCallEvent(
            run_id="run_1",
            task_id="task_1",
            turn_id=3,
            call_id="call_3",
            tool_name="run_command",
            category=ToolCallCategory.EXECUTION,
            normalized_arguments={"command": "pytest"},
            repository_state_id="state_v1",
        )

        analyzer.record_event(ev1)
        analyzer.record_event(ev2)
        analyzer.record_event(ev3)

        dists = analyzer.calculate_tool_distributions()
        self.assertEqual(analyzer.total_calls(), 3)
        self.assertIn("read_file", dists)
        self.assertIn("run_command", dists)

        rf = dists["read_file"]
        self.assertEqual(rf.total_calls, 2)
        self.assertEqual(rf.distinct_calls, 1)
        self.assertEqual(rf.repeated_calls, 1)
        self.assertEqual(rf.cache_hits, 1)
        self.assertEqual(rf.safe_redundant_calls, 1)

    # =========================================================================
    # C. Information-Value Metrics and Evidence Novelty
    # =========================================================================

    def test_information_novelty_file_read(self) -> None:
        """Novelty tracker detects new file, unchanged re-read, and modified content."""
        tracker = EvidenceHistoryTracker()

        # 1. Initial read produces NEW_EVIDENCE
        val1 = tracker.evaluate_file_read(FIXTURE_READ_PATH, FIXTURE_READ_CONTENT_V1)
        self.assertEqual(val1.novelty_class, EvidenceNovelty.NEW_EVIDENCE)
        self.assertEqual(val1.novelty_ratio, 1.0)
        self.assertEqual(val1.new_files_count, 1)

        # 2. Identical re-read produces NO_NEW_EVIDENCE
        val2 = tracker.evaluate_file_read(FIXTURE_READ_PATH, FIXTURE_READ_CONTENT_V1)
        self.assertEqual(val2.novelty_class, EvidenceNovelty.NO_NEW_EVIDENCE)
        self.assertEqual(val2.novelty_ratio, 0.0)

        # 3. Read after file content modification produces NEW_EVIDENCE with changed_files=1
        val3 = tracker.evaluate_file_read(FIXTURE_READ_PATH, FIXTURE_READ_CONTENT_V2)
        self.assertEqual(val3.novelty_class, EvidenceNovelty.NEW_EVIDENCE)
        self.assertEqual(val3.novelty_ratio, 1.0)
        self.assertEqual(val3.changed_files_count, 1)

    def test_information_novelty_graph_and_search(self) -> None:
        """Graph retrieval and semantic search return partial or new evidence depending on seen set."""
        tracker = EvidenceHistoryTracker()

        # 1. First graph query returns 3 new symbols -> NEW_EVIDENCE
        g_val1 = tracker.evaluate_graph_retrieval(FIXTURE_GRAPH_SYMBOLS_1, FIXTURE_GRAPH_RELATIONS_1)
        self.assertEqual(g_val1.novelty_class, EvidenceNovelty.NEW_EVIDENCE)
        self.assertEqual(g_val1.new_symbols_count, 3)

        # 2. Repeated graph query with same symbols -> NO_NEW_EVIDENCE
        g_val2 = tracker.evaluate_graph_retrieval(FIXTURE_GRAPH_SYMBOLS_2)
        self.assertEqual(g_val2.novelty_class, EvidenceNovelty.NO_NEW_EVIDENCE)

        # 3. Query introducing 1 new symbol and 1 seen symbol -> PARTIAL_NEW_EVIDENCE
        g_val3 = tracker.evaluate_graph_retrieval(FIXTURE_GRAPH_SYMBOLS_NEW)
        self.assertEqual(g_val3.novelty_class, EvidenceNovelty.PARTIAL_NEW_EVIDENCE)
        self.assertEqual(g_val3.new_symbols_count, 1)

    def test_information_novelty_test_execution(self) -> None:
        """Test executions evaluate novelty based on outcome, failing tests, and failure class."""
        tracker = EvidenceHistoryTracker()

        # 1. Failing test execution -> NEW_EVIDENCE
        t_val1 = tracker.evaluate_test_execution(
            command=FIXTURE_TEST_CMD,
            exit_code=FIXTURE_TEST_EXIT_CODE_FAIL,
            failing_tests=FIXTURE_TEST_FAILING_TESTS,
            error_signature=FIXTURE_TEST_ERROR_SIG,
            failure_class="INCOMPLETE_FIX",
        )
        self.assertEqual(t_val1.novelty_class, EvidenceNovelty.NEW_EVIDENCE)
        self.assertTrue(t_val1.recovery_relevant)

        # 2. Repeated test run with identical failure signature -> NO_NEW_EVIDENCE
        t_val2 = tracker.evaluate_test_execution(
            command=FIXTURE_TEST_CMD,
            exit_code=FIXTURE_TEST_EXIT_CODE_FAIL,
            failing_tests=FIXTURE_TEST_FAILING_TESTS,
            error_signature=FIXTURE_TEST_ERROR_SIG,
            failure_class="INCOMPLETE_FIX",
        )
        self.assertEqual(t_val2.novelty_class, EvidenceNovelty.NO_NEW_EVIDENCE)

        # 3. Test run transitions to PASS -> NEW_EVIDENCE
        t_val3 = tracker.evaluate_test_execution(
            command=FIXTURE_TEST_CMD,
            exit_code=FIXTURE_TEST_EXIT_CODE_PASS,
            failing_tests=FIXTURE_TEST_PASSING_TESTS,
            error_signature=FIXTURE_TEST_PASS_SIG,
        )
        self.assertEqual(t_val3.novelty_class, EvidenceNovelty.NEW_EVIDENCE)

    # =========================================================================
    # D. Success Contribution Analysis (Strictly Non-Causal)
    # =========================================================================

    def test_success_contribution_analysis_observational_only(self) -> None:
        """Success association aggregates calls cleanly and employs neutral, non-causal labeling."""
        analyzer = ToolBudgetAnalyzer()

        # task_1 succeeds
        analyzer.record_task_outcome("task_1", success=True)
        # task_2 fails
        analyzer.record_task_outcome("task_2", success=False)

        # Tool calls on task_1
        analyzer.record_event(
            ToolCallEvent(
                run_id="run_1",
                task_id="task_1",
                turn_id=1,
                call_id="c1",
                tool_name="read_file",
                category=ToolCallCategory.READ_OBSERVATION,
                normalized_arguments={"path": "src/parser.py"},
                repository_state_id="state_1",
                information_value=InformationValue(novelty_class=EvidenceNovelty.NEW_EVIDENCE),
            )
        )
        # Tool calls on task_2
        analyzer.record_event(
            ToolCallEvent(
                run_id="run_2",
                task_id="task_2",
                turn_id=1,
                call_id="c2",
                tool_name="read_file",
                category=ToolCallCategory.READ_OBSERVATION,
                normalized_arguments={"path": "src/parser.py"},
                repository_state_id="state_2",
                information_value=InformationValue(novelty_class=EvidenceNovelty.NO_NEW_EVIDENCE),
            )
        )

        assocs = analyzer.calculate_success_associations()
        rf = assocs["read_file"]
        self.assertEqual(rf.successful_task_calls, 1)
        self.assertEqual(rf.unsuccessful_task_calls, 1)
        self.assertEqual(rf.new_evidence_on_success, 1)
        self.assertEqual(rf.new_evidence_on_failure, 0)

        # Markdown report must contain non-causal disclaimer alert
        report = analyzer.generate_markdown_report()
        self.assertIn("Correlations between tool invocation and task success are strictly observational", report)
        self.assertNotIn("caused the solution", report)

    # =========================================================================
    # E. Wasteful Call Detection and Classification
    # =========================================================================

    def test_waste_detection_categories(self) -> None:
        """WasteDetector accurately identifies SAFE_REDUNDANT, NECESSARY_REPEAT, and UNKNOWN."""
        detector = WasteDetector()
        repo_state = "manifest_abc123"

        # 1. Initial read in this state -> UNKNOWN (never penalized as redundant on 1st call)
        c1 = detector.classify_call(
            tool_name="read_file",
            arguments={"path": "src/parser.py"},
            repository_state_id=repo_state,
        )
        self.assertEqual(c1, WasteClassification.UNKNOWN)

        # 2. Second identical read under unchanged state -> SAFE_REDUNDANT
        c2 = detector.classify_call(
            tool_name="read_file",
            arguments={"path": "src/parser.py"},
            repository_state_id=repo_state,
        )
        self.assertEqual(c2, WasteClassification.SAFE_REDUNDANT)

        # 3. Third read after file modification -> NECESSARY_REPEAT
        c3 = detector.classify_call(
            tool_name="read_file",
            arguments={"path": "src/parser.py"},
            repository_state_id=repo_state,
            after_mutation=True,
        )
        self.assertEqual(c3, WasteClassification.NECESSARY_REPEAT)

        # 4. Command retry after transient error -> NECESSARY_REPEAT
        c4 = detector.classify_call(
            tool_name="run_command",
            arguments={"command": "pytest tests/"},
            repository_state_id=repo_state,
            had_transient_error=True,
        )
        self.assertEqual(c4, WasteClassification.NECESSARY_REPEAT)

    # =========================================================================
    # F. Bounded Tool Cache Correctness and Targeted Invalidation
    # =========================================================================

    def test_cache_hit_and_targeted_invalidation(self) -> None:
        """BoundedToolCache returns hits under identical state, and invalidates affected files on edit."""
        cache = BoundedToolCache(max_entries=50)
        repo_state_1 = "state_hash_1"

        k_parser = cache.make_cache_key("read_file", {"path": "src/parser.py"}, repo_state_1)
        k_readme = cache.make_cache_key("read_file", {"path": "README.md"}, repo_state_1)
        k_status = cache.make_cache_key("get_status", {}, repo_state_1)

        cache.put(k_parser, "parser content v1")
        cache.put(k_readme, "readme content")
        cache.put(k_status, "working tree clean")

        # 1. Cache hit under unchanged state
        self.assertEqual(cache.get(k_parser), "parser content v1")
        self.assertEqual(cache.get(k_readme), "readme content")
        self.assertEqual(cache.hits_count, 2)

        # 2. Mutate src/parser.py -> repo_state shifts to state_hash_2
        repo_state_2 = "state_hash_2"
        inval_count = cache.invalidate_for_mutation(mutated_path="src/parser.py", new_repository_state_id=repo_state_2)

        # 2 entries invalidated: src/parser.py and get_status
        self.assertEqual(inval_count, 2)

        # Read of mutated parser is a cache miss
        k_parser_v2 = cache.make_cache_key("read_file", {"path": "src/parser.py"}, repo_state_2)
        self.assertIsNone(cache.get(k_parser_v2))

        # Status is a cache miss
        k_status_v2 = cache.make_cache_key("get_status", {}, repo_state_2)
        self.assertIsNone(cache.get(k_status_v2))

        # Unrelated README read on repo_state_1 remains cached
        self.assertEqual(cache.get(k_readme), "readme content")

    def test_mutations_and_submissions_never_cached(self) -> None:
        """edit_file, write_file, and submit_patch must NEVER be stored in the cache."""
        cache = BoundedToolCache()
        k_edit = cache.make_cache_key("edit_file", {"path": "src/parser.py", "content": "..."}, "s1")
        k_write = cache.make_cache_key("write_file", {"path": "src/parser.py", "content": "..."}, "s1")
        k_sub = cache.make_cache_key("submit_patch", {}, "s1")

        self.assertFalse(cache.is_tool_cacheable("edit_file"))
        self.assertFalse(cache.is_tool_cacheable("write_file"))
        self.assertFalse(cache.is_tool_cacheable("submit_patch"))

        self.assertIsNone(cache.put(k_edit, "patch applied"))
        self.assertIsNone(cache.put(k_write, "written"))
        self.assertIsNone(cache.put(k_sub, "submitted"))
        self.assertEqual(cache.size(), 0)

    # =========================================================================
    # G. Cache Bounds and LRU Eviction
    # =========================================================================

    def test_cache_capacity_and_lru_eviction(self) -> None:
        """Cache enforces max_entries capacity bound and evicts least recently accessed entry."""
        cache = BoundedToolCache(max_entries=2)
        k1 = cache.make_cache_key("read_file", {"path": "file1.py"}, "s1")
        k2 = cache.make_cache_key("read_file", {"path": "file2.py"}, "s1")
        k3 = cache.make_cache_key("read_file", {"path": "file3.py"}, "s1")

        cache.put(k1, "content1")
        cache.put(k2, "content2")
        self.assertEqual(cache.size(), 2)

        # Access k1 to make k2 the LRU entry
        cache.get(k1)

        # Put k3: triggers eviction of k2
        cache.put(k3, "content3")
        self.assertEqual(cache.size(), 2)
        self.assertEqual(cache.evictions_count, 1)

        # k1 and k3 are present; k2 is evicted
        self.assertIsNotNone(cache.get(k1))
        self.assertIsNotNone(cache.get(k3))
        self.assertIsNone(cache.get(k2))

    # =========================================================================
    # H. Stage 25 Integration (Fingerprints, File Tracking)
    # =========================================================================

    def test_stage25_fingerprints_and_tracking_reuse(self) -> None:
        """Stage 26 budgeting reuses Stage 25 fingerprinting and ChangedFileTracker seamlessly."""
        tracker = ChangedFileTracker()
        rec, is_new = tracker.record_file_observation("src/parser.py", FIXTURE_READ_CONTENT_V1)
        self.assertTrue(is_new)

        digest1 = tracker.get_manifest_digest()
        self.assertIsNotNone(digest1)

        # Record mutation in Stage 25 tracker
        tracker.mark_file_edit("src/parser.py", FIXTURE_READ_CONTENT_V2)
        digest2 = tracker.get_manifest_digest()
        self.assertNotEqual(digest1, digest2)

    def test_repeated_directory_status_unchanged(self) -> None:
        """Repeated get_status on unchanged repo produces NO_NEW_EVIDENCE and SAFE_REDUNDANT."""
        tracker = EvidenceHistoryTracker()
        detector = WasteDetector()
        repo_state = "manifest_v1"

        # 1. First status
        v1 = tracker.evaluate_status_observation(FIXTURE_STATUS_OUTPUT_1)
        w1 = detector.classify_call("get_status", {}, repo_state)
        self.assertEqual(v1.novelty_class, EvidenceNovelty.NEW_EVIDENCE)
        self.assertEqual(w1, WasteClassification.UNKNOWN)

        # 2. Second status under unchanged repo
        v2 = tracker.evaluate_status_observation(FIXTURE_STATUS_OUTPUT_2)
        w2 = detector.classify_call("get_status", {}, repo_state)
        self.assertEqual(v2.novelty_class, EvidenceNovelty.NO_NEW_EVIDENCE)
        self.assertEqual(w2, WasteClassification.SAFE_REDUNDANT)

    def test_semantic_search_unchanged_index(self) -> None:
        """Repeated semantic query with identical candidates produces NO_NEW_EVIDENCE."""
        tracker = EvidenceHistoryTracker()
        v1 = tracker.evaluate_search_results(FIXTURE_SEARCH_CANDIDATES_1)
        self.assertEqual(v1.novelty_class, EvidenceNovelty.NEW_EVIDENCE)

        v2 = tracker.evaluate_search_results(FIXTURE_SEARCH_CANDIDATES_2)
        self.assertEqual(v2.novelty_class, EvidenceNovelty.NO_NEW_EVIDENCE)

        v3 = tracker.evaluate_search_results(FIXTURE_SEARCH_CANDIDATES_NEW)
        self.assertEqual(v3.novelty_class, EvidenceNovelty.PARTIAL_NEW_EVIDENCE)

    def test_repeated_full_test_run_vs_rerun_after_edit(self) -> None:
        """Repeated test run on unchanged source is POSSIBLY_REDUNDANT; rerun after edit is NECESSARY_REPEAT."""
        detector = WasteDetector()
        repo_state_1 = "repo_state_1"

        # 1st run
        detector.classify_call("run_command", {"command": FIXTURE_TEST_CMD}, repo_state_1)

        # 2nd run without edit
        w2 = detector.classify_call("run_command", {"command": FIXTURE_TEST_CMD}, repo_state_1)
        self.assertEqual(w2, WasteClassification.POSSIBLY_REDUNDANT)

        # 3rd run after source edit
        w3 = detector.classify_call("run_command", {"command": FIXTURE_TEST_CMD}, repo_state_1, after_mutation=True)
        self.assertEqual(w3, WasteClassification.NECESSARY_REPEAT)

    def test_legitimate_recovery_rerun(self) -> None:
        """Rerunning verification under active recovery is classified as NECESSARY_REPEAT."""
        detector = WasteDetector()
        repo_state = "repo_state_1"
        detector.classify_call("run_command", {"command": FIXTURE_TEST_CMD}, repo_state)

        # Retry marked during recovery
        w_rec = detector.classify_call("run_command", {"command": FIXTURE_TEST_CMD}, repo_state, is_retry=True)
        self.assertEqual(w_rec, WasteClassification.NECESSARY_REPEAT)

    def test_insufficient_data_association(self) -> None:
        """When 0 tasks are resolved, success association status is INSUFFICIENT_DATA."""
        analyzer = ToolBudgetAnalyzer()
        analyzer.record_event(
            ToolCallEvent(
                run_id="run_unresolved",
                task_id="task_unresolved",
                turn_id=1,
                call_id="c1",
                tool_name="read_file",
                category=ToolCallCategory.READ_OBSERVATION,
                normalized_arguments={"path": "src/parser.py"},
                repository_state_id="state_1",
            )
        )
        assocs = analyzer.calculate_success_associations()
        self.assertEqual(assocs["read_file"].association_status, ToolAssociation.INSUFFICIENT_DATA)

    def test_cross_tool_argument_normalization(self) -> None:
        """Various tool arguments normalize deterministically without data loss."""
        # 1. search_similar_code query lowercasing
        n1 = normalize_arguments("search_similar_code", {"query": "  ParseQuery  ", "k": 5})
        self.assertEqual(n1["query"], "parsequery")
        self.assertEqual(n1["k"], 5)

        # 2. get_code_subgraph seed sorting
        n2 = normalize_arguments("get_code_subgraph", {"seeds": ["beta", "alpha", "gamma"]})
        self.assertEqual(n2["seeds"], ["alpha", "beta", "gamma"])

        # 3. edit_file path normalization
        n3 = normalize_arguments("edit_file", {"path": "src\\utils.py", "old_str": "foo", "new_str": "bar"})
        self.assertEqual(n3["path"], "src/utils.py")

    # =========================================================================
    # I. E9 / E10 / E11 Regression Preservation
    # =========================================================================

    def test_e9_e10_e11_semantics_unchanged(self) -> None:
        """Failure classification, progress detection, and recovery paths execute with intact semantics."""
        # 1. E9 Classifier
        classifier = FailureClassifierV1()
        self.assertIsNotNone(classifier)

        # 2. E10 Progress detector
        detector = NoProgressDetectorV1(threshold=2)
        self.assertEqual(detector.threshold, 2)

        # 3. E11 Recovery controller
        controller = RecoveryControllerV1()
        ctx = RecoveryContext(
            failure_classification=FailureClass.WRONG_HYPOTHESIS.value,
            progress_status=ProgressStatus.NO_PROGRESS.value,
            no_progress_reason=NoProgressReason.REPEATED_HYPOTHESIS.value,
            test_result="FAILED",
            diff_inspected=True,
        )
        decision = controller.route_recovery(ctx)
        self.assertEqual(decision.selected_path, RecoveryPath.TEST_FAILURE)
        self.assertEqual(decision.action, RecoveryActionType.REVISE_HYPOTHESIS)

    # =========================================================================
    # J. Security and Credential Scrubbing
    # =========================================================================

    def test_secret_scrubbing_in_arguments(self) -> None:
        """Sensitive tokens in command strings are sanitized before storage in normalized arguments."""
        norm_args = normalize_arguments("run_command", {"command": FIXTURE_CMD_WITH_SECRET})
        clean_cmd = norm_args["command"]

        self.assertNotIn("ghp_1234567890abcdef1234567890abcdef1234", clean_cmd)
        self.assertIn("[REDACTED_SECRET]", clean_cmd)
        # Normal command target remains intact
        self.assertIn("tests/test_auth.py", clean_cmd)

    # =========================================================================
    # K. Stage 24 Invariance Verification
    # =========================================================================

    def test_frozen_specialist_and_topology_hashes(self) -> None:
        """Verifies that Scout, Debugger, Reviewer, and Stage 24 topology prompts remain frozen."""
        scout_yaml = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "sub_agents" / "scout.yaml"
        scout_prompt = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "prompts" / "scout.md"
        debugger_yaml = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "sub_agents" / "debugger.yaml"
        debugger_prompt = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "prompts" / "debugger.md"
        reviewer_yaml = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "sub_agents" / "reviewer.yaml"
        reviewer_prompt = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "prompts" / "reviewer.md"

        self.assertEqual(sha256_file(scout_yaml), FROZEN_SCOUT_YAML_SHA256)
        self.assertEqual(sha256_file(scout_prompt), FROZEN_SCOUT_PROMPT_SHA256)
        self.assertEqual(sha256_file(debugger_yaml), FROZEN_DEBUGGER_YAML_SHA256)
        self.assertEqual(sha256_file(debugger_prompt), FROZEN_DEBUGGER_PROMPT_SHA256)
        self.assertEqual(sha256_file(reviewer_yaml), FROZEN_REVIEWER_YAML_SHA256)
        self.assertEqual(sha256_file(reviewer_prompt), FROZEN_REVIEWER_PROMPT_SHA256)

        # Topology shared prompt
        for m_id in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            prompt_file = PROJECT_ROOT / "experiments" / "candidates" / m_id / "prompts" / "root.md"
            self.assertEqual(sha256_file(prompt_file), FROZEN_TOPOLOGY_SHARED_PROMPT_SHA256)


if __name__ == "__main__":
    unittest.main()
