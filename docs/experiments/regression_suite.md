# IMPULSE Failure Regression Suite (Stage 45)

## 1. Executive Summary & Purpose

The IMPULSE Failure Regression Suite provides a candidate-independent, durable verification mechanism that systematically captures every general failure mode discovered across the IMPULSE engineering lifecycle. Its primary goal is to ensure that behavioral, orchestration, packaging, tool-discipline, recovery, retrieval, testing, and submission-discipline pathologies never silently return in candidate iterations (M0–M5, R1–R4, T0–T3, REC0–REC3, etc.).

As mandated by PLAN.md:
> *"Whenever a task reveals a general failure mode, add a regression case to the development suite."*

The suite guarantees:
1. **Zero Fabrication:** No model outputs, synthetic traces, or live GPU metrics are invented or claimed without verified execution.
2. **Honest Blocked Preservations:** Failures requiring inaccessible resources (such as 31B long-context execution or air-gapped Kaggle container networking) are preserved explicitly as `BLOCKED`, never deceptively passed.
3. **Cryptographic Held-Out Protection:** Tasks belonging to the frozen held-out benchmark split (`benchmark/splits/v1/held_out.lock`) are strictly prohibited from entering development or regression manifests.
4. **Candidate Independence:** Tests verify architectural invariants and behavioral policies independently of any specific candidate model weights.

---

## 2. Regression Classification & Taxonomy

Each regression case belongs to one of four execution tiers:

| Regression Type | Description | Current Count |
| :--- | :--- | :---: |
| `FULL_TASK_REGRESSION` | Complete end-to-end benchmark tasks from the open development split. Reserved in schema; zero fabricated without live GPU model verification. | 0 |
| `HARNESS_REGRESSION` | Deterministic component-level and orchestration harness tests verifying policies, loop detectors, diff scopes, and file hygiene without model inference. | 19 |
| `INFRASTRUCTURE_REGRESSION` | Deterministic checks enforcing infrastructure invariants, manifest hashes, and cryptographic split locks. | 1 |
| `UNREPRESENTED_BLOCKED_FAILURE` | Conceptually and historically observed failures that lack local CPU execution artifacts; preserved honestly as `BLOCKED`. | 2 |
| **Total** | | **22** |

---

## 3. The 8 Core Plan Failure Modes Covered

Stage 45 explicitly implements coverage for the general failure modes identified in PLAN.md:

1. **Semantic Search Misleads Agent (`REG-RETRIEVAL-001`):**
   - *Failure:* Weak semantic search candidates deceive localization away from actual root cause.
   - *Invariant:* R1 policy mandates fallback to `EXACT_SEARCH` when similarity is below threshold (0.50), preventing blind expansion.
2. **Semantic Retrieval Budget Exhaustion (`REG-RETRIEVAL-002`):**
   - *Failure:* Unbounded semantic retrieval calls bloat prompt context.
   - *Invariant:* Hard bounds on `max_semantic_calls` (3) and `max_retrieved_items` (15); terminates with `STOP_RETRIEVAL`.
3. **Agent Edits Before Reading Tests/Evidence (`REG-POLICY-001`):**
   - *Failure:* Agent jumps directly into modifying code without inspecting repository layout or test failures.
   - *Invariant:* State machine requires `exact_recon_completed == True` before hypothesis formulation or edit triggering.
4. **Agent Loops on Failing Test (`REG-RECOVERY-001` to `REG-RECOVERY-005`):**
   - *Failure:* Repeated commands, identical error traces, identical edits, or oscillating actions (A -> B -> A -> B).
   - *Invariant:* `NoProgressDetectorV1` and `RecoveryLoopDetector` flag `NO_PROGRESS` and `LOOP_DETECTED` within 2 cycles.
5. **Agent Leaves Temporary File (`REG-HYGIENE-001`):**
   - *Failure:* Scratch scripts (`scratch_work.py`), temporary patches (`temp.patch`), or debug logs left in repository.
   - *Invariant:* Diff discipline detectors identify scratch artifacts for removal; `SafeCleaner` enforces safe cleanup of untracked files while protecting tracked files.
6. **Agent Changes Unrelated File (`REG-DIFF-001`):**
   - *Failure:* Accidental modification of files outside defect scope (e.g. `.github/workflows/ci.yml`).
   - *Invariant:* Reviewer rules evaluate modified file scope and issue blocking finding `CHANGES_REQUESTED`.
7. **Agent Fails to Inspect Caller (`REG-GRAPH-001`):**
   - *Failure:* Modifying a public contract symbol without checking caller dependencies.
   - *Invariant:* `NeighborPolicyV1` requires relational caller/callee exploration for contract-sensitive candidates while blocking context-exploding consecutive expansions.
8. **Agent Stops After First Red Test (`REG-TESTING-001`):**
   - *Failure:* Prematurely declaring failure or stopping after the first failing test without escalating to adjacent or subsystem validation.
   - *Invariant:* Test policies T1/T2 require `escalate_on_targeted_failure == True` and forbid stopping on failure as pass.
9. **Agent Submits Without Final Diff Review (`REG-SUBMISSION-001`):**
   - *Failure:* Calling `submit_patch` without reviewing git status, hygiene, or verification results.
   - *Invariant:* `is_review_ready` strictly rejects submission readiness if verification is unattempted or candidate diff is empty.

---

## 4. Stage 35 Recovery Taxonomy Coverage Matrix

All 10 recovery patterns from Stage 35 are explicitly addressed:

| Recovery Pattern | Regression ID | Type | Expected Invariant & Recovery Behavior |
| :--- | :--- | :--- | :--- |
| `REPEATED_COMMAND` | `REG-RECOVERY-001` | HARNESS | Flags `NO_PROGRESS` at threshold=2 cycles on identical command. |
| `REPEATED_ERROR` | `REG-RECOVERY-002` | HARNESS | Detects identical failure signature across cycles without new evidence. |
| `REPEATED_EDIT` | `REG-RECOVERY-003` | HARNESS | Normalizes diffs to detect materially identical code edits. |
| `REPEATED_HYPOTHESIS` | `REG-RECOVERY-004` | HARNESS | Identifies unrevised hypothesis pursued across cycles. |
| `RECOVERY_LOOP` | `REG-RECOVERY-005` | HARNESS | Detects alternating oscillating recovery actions (A -> B -> A -> B). |
| `RECOVERY_THRASHING` | `REG-RECOVERY-006` | HARNESS | Tracks consecutive unverified recovery actions without diagnostic progress. |
| `RETRY_WASTE` | `REG-RECOVERY-007` | HARNESS | Enforces `BUDGET_EXHAUSTED` once retry attempts exceed configured budget. |
| `RECOVERY_OMISSION` | `REG-RECOVERY-008` | HARNESS | Requires explicit failure classification and fallback assignment on failure. |
| `LATE_RECOVERY` | `REG-RECOVERY-009` | HARNESS | Enforces early detection with no-progress threshold bounded to <= 3 turns. |
| `FAILED_RECOVERY` | `REG-RECOVERY-010` | HARNESS | Escalates failed primary action to alternate path (`RETRY_THEN_ALTERNATE`). |

---

## 5. Schema & Provenance Structure

Each regression case is defined by the typed `RegressionCase` contract:

```python
@dataclass
class RegressionCase:
    regression_id: str             # e.g., "REG-RETRIEVAL-001"
    version: str                   # SemVer, e.g. "1.0.0"
    title: str                     # Human-readable title
    category: RegressionCategory   # RETRIEVAL, RECOVERY, POLICY, etc.
    regression_type: RegressionType# HARNESS, INFRASTRUCTURE, UNREPRESENTED_BLOCKED
    severity: RegressionSeverity   # CRITICAL, HIGH, MEDIUM, LOW
    source_failure_type: str       # Mapped failure class
    description: str               # Detailed pathology description
    observed_or_synthetic: str     # "observed", "synthetic", "architectural_invariant", "blocked_environment"
    provenance: dict               # Origin stage, source files, candidate IDs, historical context
    fixture_type: str              # harness_policy, harness_detector, harness_filesystem, etc.
    expected_invariants: list[str] # Concrete assertions verified during execution
    execution_entrypoint: str      # Module:function path to invariant checker
    required_capabilities: list[str] # Hardware/runtime requirements
    status: RegressionStatus       # ACTIVE, BLOCKED, DEPRECATED
    created_from_stage: str        # e.g., "Stage 45"
    created_from_commit: str       # Parent commit SHA
    related_candidate_ids: list[str]# M0, R1, T1, REC0, etc.
    signature: str                 # Canonical signature for deduplication
```

### Manifest Persistence
The catalog is stored in `experiments/regressions/manifest.json` and mirrored in individual case JSON files under `experiments/regressions/cases/`. The manifest contains a SHA-256 integrity hash of all cases in canonical order to detect unauthorized manual edits.

---

## 6. Execution Commands & Runner Semantics

The suite provides two execution entrypoints that delegate to the same core engine:

### CLI Runner
```bash
# Execute all regressions
python scripts/run_regressions.py --all

# Execute single regression by ID
python scripts/run_regressions.py --id REG-HYGIENE-001

# Validate catalog integrity, deduplication, and held-out locks
python scripts/run_regressions.py --validate

# Generate Stage 45 markdown report
python scripts/run_regressions.py --report

# List all registered regressions
python scripts/run_regressions.py --list
```

### Unittest Discovery Runner
```bash
python -m unittest discover tests/regressions
```

### Status Meanings
- **`PASS`:** The deterministic invariant checker executed and passed all assertions.
- **`FAIL`:** An invariant was violated or an unhandled exception occurred (runner exits with code 1).
- **`BLOCKED`:** The test verified that necessary hardware/runtime prerequisites are honestly missing; zero execution was faked.
- **`SKIPPED`:** The test is marked `DEPRECATED` and deliberately omitted from active gating.

---

## 7. Held-Out Protection Gate

The benchmark dataset splits defined in Stage 29 establish a strict boundary between open development tasks and locked held-out evaluation tasks (`benchmark/splits/v1/held_out.lock`).

The regression system enforces:
1. `validate_task_not_held_out(task_id)` queries the cryptographic lock file.
2. If any regression case, manifest, or execution trace references a held-out task ID, `HeldOutContaminationError` is raised immediately.
3. Automated catalog validation scans all case titles, descriptions, and provenance records to guarantee zero leakage.

---

## 8. Lifecycle of Discovered Failures

When a future stage or evaluation run discovers a new general failure mode:
1. **Catalog Addition:** Add a new `RegressionCase` to `local/regressions/catalog.py` with a unique ID and canonical failure signature.
2. **Invariant Checker:** Implement the deterministic verification function under `local/regressions/invariants/`.
3. **Deduplication Check:** Run `python scripts/run_regressions.py --validate` to verify that the ID and failure signature do not collide with existing cases.
4. **Graduation:** If live cluster evaluation provides an executable, open-split benchmark task reproducing the failure, the case may graduate from `HARNESS_REGRESSION` or `UNREPRESENTED_BLOCKED_FAILURE` to `FULL_TASK_REGRESSION`.
