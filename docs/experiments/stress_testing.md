# IMPULSE — Stress Testing Suite Documentation (Stage 46)

## 1. Stage Objective

The IMPULSE Stress Testing Suite evaluates agent components, decision policies, and orchestration mechanics under challenging operational conditions before candidate release. 

While Stage 45 built an immutable regression suite for previously observed failures, Stage 46 subjects the agent to synthetic, resource-bounded stress vectors across 11 key operational dimensions.

The suite establishes an explicit boundary between two separate questions:
1. **Do deterministic components and engineering controls behave correctly under stress?** (Demonstrated deterministically: **PASS**)
2. **Have we demonstrated that the live model-driven agent solves tasks under these conditions?** (Unrepresented on CPU development host: **BLOCKED**)

---

## 2. Stress Schema and Catalog Architecture

The stress framework is organized cleanly under:
- `local/stress/`:
  - `models.py`: Typed enums (`StressCategory`, `StressType`, `StressResultStatus`), `StressCase`, `StressManifest`, and `StressSuiteSummary`.
  - `fixtures.py`: Resource-bounded, hermetic fixture generators.
  - `catalog.py`: The canonical registry of 22 stress cases and catalog validator.
  - `runner.py`: Deterministic test runner and summary aggregator.
  - `reporting.py`: Empirical report generator.
  - `invariants/`: Modular invariant checkers for each stress family.
- `experiments/stress/`:
  - `manifest.json`: Authoritative catalog manifest with SHA-256 integrity digest.
  - `cases/*.json`: 22 serialized case definitions.
  - `stage46_report.md`: Formal Stage 46 empirical verification report.
- `scripts/run_stress_tests.py`: CLI interface for listing, validating, running, and reporting stress tests.
- `tests/stress/test_harness_stress.py`: Native `unittest` discovery adapter for all 22 registered cases.
- `tests/test_stress_stage46.py`: Comprehensive focused test suite (20 tests covering manifest integrity, negative validation, held-out protections, and bounding).

---

## 3. The 11 Required Stress Families

| # | Stress Family | Case ID(s) | Tier | Primary Invariant Verified |
| :-: | :--- | :--- | :--- | :--- |
| 1 | Very Large Repository | `STRESS-REPO-001` | Component | Safe traversal of 120 files across 3 directory tiers; strict path containment within fixture root; bounded runtime (<5s); zero leaked files. |
| 2 | Ambiguous Issue Wording | `STRESS-AMBIGUOUS-001`<br>`STRESS-LIVE-AMBIGUOUS-001` | Policy<br>Live Model | Ambiguous wording halts immediate speculative edits and routes to bounded reconnaissance probes.<br>Live model cognitive disambiguation honestly BLOCKED. |
| 3 | Misleading Function Names | `STRESS-MISLEADING-001`<br>`STRESS-LIVE-MISLEADING-001` | Component<br>Live Model | AST inspection and test assertion failure expose semantic contradictions where function name implies addition but body performs multiplication.<br>Live model reasoning honestly BLOCKED. |
| 4 | Multi-File Fix | `STRESS-MULTIFILE-001` | Component | Multi-file fix spanning service and test contracts captured without dropping hunks; intermediary files untainted; applied cleanly to fresh workspace. |
| 5 | Hidden Dependency Relationship | `STRESS-GRAPH-001` | Component | Discovers indirect dependency through 3 relational hops (`entrypoint` -> `dispatcher` -> `registry` -> `hidden_handler`) within bounded neighbor limit (`max_retained <= 5`). |
| 6 | Failing Test with Long Logs | `STRESS-LOG-001` | Component | 50,000+ byte verbose test log compacted to <= 1,500 chars while preserving initial `KeyError` traceback and final failure summary. |
| 7 | Pre-Existing Failing Test | `STRESS-PREEXISTING-001` | Component | Evaluator isolates pre-existing legacy test failure from candidate change; target bug classified as `RESOLVED` with zero false regressions. |
| 8 | Required New File | `STRESS-NEWFILE-001` | Component | Fix requiring an untracked new file stages intent via `git add -N .`, extracts patch with `/dev/null` addition, and reconstitutes new file on clean copy. |
| 9 | Binary or Unusual File Intent | `STRESS-BINARY-001` | Component | Null-byte and invalid UTF-8 bytes detected; direct text decoding rejected without silent corruption; diagnostic preview formatted safely without dumping control chars. |
| 10 | Repeated Test Failure (10 Stage 35 Patterns) | `STRESS-RECOVERY-001` to `010` | Component & Policy | Covers all 10 patterns: `REPEATED_COMMAND`, `REPEATED_ERROR`, `REPEATED_EDIT`, `REPEATED_HYPOTHESIS`, `RECOVERY_LOOP`, `RECOVERY_THRASHING`, `RETRY_WASTE`, `RECOVERY_OMISSION`, `LATE_RECOVERY`, `FAILED_RECOVERY`. |
| 11 | Expensive Full-Suite Tests | `STRESS-EXPENSIVE-001` | Policy | When estimated suite runtime (1,800s) exceeds budget (300s), evaluator deterministically marks full suite `NOT_FEASIBLE` and prioritizes targeted validation. |

---

## 4. Fixture Generation and Resource Bounding

All fixtures are generated dynamically during execution inside isolated temporary directories (`tempfile.mkdtemp`):
1. **Zero External Dependencies**: Standard library and existing repository tools only.
2. **Complete Disposal**: All temporary git workspaces and log files are purged in `finally` blocks, including Windows read-only git file handling (`stat.S_IWRITE`).
3. **Resource Caps**:
   - Repository size capped to `<= 1000` files.
   - Directory depth capped to `<= 10`.
   - Log compaction capped to `MAX_OUTPUT_SUMMARY_LENGTH = 1500`.
   - Graph neighbor retention capped to `max_retained = 5`.
   - Retry budget capped to explicit thresholds (e.g. `<= 3` attempts).
4. **Held-Out Protection**: Zero locked held-out tasks (`benchmark/splits/v1/held_out.lock`) are ever used as stress fixtures.

---

## 5. Execution Semantics: PASS vs BLOCKED vs FAIL

- **PASS**: The stated stress scenario executed deterministically and all required invariants held.
- **FAIL**: A scenario executed and at least one required invariant was violated.
- **BLOCKED**: The scenario requires an environment, model capability, or hardware accelerator unavailable on the current host.
  - On the local CPU host, live Gemma 4 31B inference is unavailable.
  - Scenarios testing live model cognitive disambiguation (`STRESS-LIVE-AMBIGUOUS-001`, `STRESS-LIVE-MISLEADING-001`) return `BLOCKED`.
  - In `unittest` discovery, the test asserts `res.status == StressResultStatus.BLOCKED`. This verifies that the blocker-handling contract functions correctly without fabricating model capability.
- **SKIPPED**: The scenario was deliberately omitted by profile selection or deprecation.

---

## 6. CLI Usage Guide

Run stress tests locally using `scripts/run_stress_tests.py`:

```bash
# Validate catalog integrity, deduplication, and manifest hash
python scripts/run_stress_tests.py --validate

# List all 22 registered stress test cases
python scripts/run_stress_tests.py --list

# Execute all stress tests (normal profile)
python scripts/run_stress_tests.py --all

# Execute a specific stress test case by ID
python scripts/run_stress_tests.py --id STRESS-LOG-001

# Filter execution by category
python scripts/run_stress_tests.py --category LARGE_REPO

# Filter execution by tier
python scripts/run_stress_tests.py --type DETERMINISTIC_COMPONENT

# Generate authoritative markdown report
python scripts/run_stress_tests.py --report

# Output machine-readable JSON
python scripts/run_stress_tests.py --all --json
```

---

## 7. How to Register a New Stress Case

1. Add a new `StressCase` definition in `local/stress/catalog.py`:
   - Unique `stress_id` (e.g. `STRESS-CUSTOM-001`).
   - Valid `StressCategory` and `StressType`.
   - Valid entrypoint string `module:function`.
   - Valid Stage 45 regression ID references in `related_regression_ids`.
   - Explicit `expected_invariants` and `resource_limits`.
2. Implement the invariant checker function in `local/stress/invariants/`:
   - Must return `tuple[bool, str, dict[str, Any]]` representing `(passed, rationale, details)`.
   - Must guarantee cleanup of any temporary directories.
3. Add a corresponding test method in `tests/stress/test_harness_stress.py`.
4. Run `python scripts/run_stress_tests.py --validate` and `python scripts/run_stress_tests.py --report` to update `manifest.json` and `stage46_report.md`.
