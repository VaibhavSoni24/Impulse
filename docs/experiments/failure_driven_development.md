# IMPULSE Failure-Driven Development (FDD) Loop

## 1. Purpose and Philosophy

The **Failure-Driven Development (FDD) Loop** (Stage 31) provides an evidence-based, deterministic experimental control harness around the IMPULSE evaluation system. Rather than introducing speculative or ungrounded agent modifications, every change within IMPULSE must answer a single central question:

> *"Which failure mode did this change target, and did that failure mode actually decrease?"*

Stage 31 establishes the operational machinery to collect failures, cluster them deterministically, select the highest-value failure cluster, formulate a single-hypothesis intervention, and evaluate it through a disciplined **Smoke → Validation → Held-Out** gating pipeline.

Stage 31 builds the **experimental loop**; it does not implement prompt optimizations (Stage 32), retrieval optimizations (Stage 33), recovery optimizations (Stage 35), or LoRA fine-tuning (Stage 37+).

---

## 2. Authoritative Data Sources

The FDD loop ingests evaluation records directly from existing project storage:
- SQLite Evaluation Database: `experiments/evaluation.db`
- Evaluation results files: `experiments/baseline/<candidate>/results.jsonl`
- Stage 30 Failure Dashboard artifacts: `experiments/dashboard/<candidate>/<split>/`
- Benchmark splits: `benchmark/splits/v1/`

No secondary or duplicate databases are created.

---

## 3. Failure Normalization and Actionability

Raw evaluation run summaries and execution records are normalized into typed `FailureRecord` instances:
- Preserves raw evidence references (`source_record_reference`, `run_id`, `task_id`).
- Normalizes canonical failure category (`FailureClass`) and evaluator failure stage (`FailureStage`).
- Determines cognitive actionability:
  - Runs with status `execution_unavailable_local_host`, `UNAVAILABLE`, or hardware limits (e.g. lack of local GPU for 31B model) are classified with `is_actionable = False`.
  - Only executed runs in `LIVE` or `FIXTURE` mode with real cognitive failure outcomes have `is_actionable = True`.
- Strict separation prevents infrastructure limits from being misinterpreted as agent reasoning defects.

---

## 4. Deterministic Failure Clustering

The clustering engine (`local/fdd/clustering.py`) groups normalized failure records using:
1. Canonical failure category (e.g., `WRONG_HYPOTHESIS`, `COMMAND`, `INCOMPLETE_FIX`).
2. Evaluator failure stage (e.g., `AGENT_EXECUTION`, `PATCH_APPLICATION`, `VERIFICATION`).
3. Primary termination signature.

### Guarantees
- **Permutation Invariance:** Records supplied in any order produce identical cluster contents and ordering.
- **Deterministic Identifiers:** Cluster IDs follow the scheme `cls_{category}_{stage}_{sig_hash}`.
- **Actionable Isolation:** Clusters separate eligible completed runs from unavailable/infrastructure runs.

---

## 5. Prioritization Policy: Highest-Value Cluster

Selection of the highest-value cluster (`local/fdd/prioritization.py`) follows a documented lexicographic ranking:
1. **Eligible completed live failure count** (descending)
2. **Unique affected task count** (descending)
3. **Repository coverage count** (descending)
4. **Deterministic `cluster_id`** (ascending tie-breaker)

### First-Class "No Live Data" Handling
In the current development environment, the local Windows host cannot execute the 31B Gemma 4 competition model; baseline records reflect infrastructure unavailability. When prioritizing production runs without live completed inference:
- `selected_cluster = None`
- `selection_status = NO_ACTIONABLE_LIVE_FAILURES`
- Zero live benchmark outcomes are fabricated.

---

## 6. Single-Hypothesis Intervention Model

Every FDD iteration executes exactly **ONE** intervention (`local/fdd/interventions.py`):
- Typed record specifying: `intervention_id`, `source_cluster_id`, `target_failure_mode`, `hypothesis`, `expected_behavior_change`, `intervention_scope`, `changed_dimensions`, `affected_files`, `baseline_candidate`, `candidate_id`, `smoke_tasks`, `validation_split`, `held_out_policy`.
- **Single-Dimension Discipline:** An intervention must modify only one major architectural or configuration dimension (e.g., `PROMPT`, `RETRIEVAL`, `TESTING`, `RECOVERY`, `TOPOLOGY`, `SKILL`). Bundling unrelated changes (e.g., prompt tweak + retrieval top_k + LoRA) is strictly rejected.
- **Candidate Isolation:** The baseline candidate is never mutated in place (`baseline_candidate != candidate_id`). New candidates reside in dedicated directories.
- **Frozen Artifact Protection:** Any intervention attempting to modify frozen Stage 24 specialist YAMLs, prompts, or skills is rejected immediately.

---

## 7. Clean-Copy Evaluation Lifecycle

Evaluation rounds reuse the authoritative Stage 28 `CleanCopyEvaluator` (`local/clean_copy/evaluator.py`):
1. **Clean Snapshot:** Create isolated snapshot from baseline.
2. **Candidate Execution:** Load candidate configuration and execute agent adapter.
3. **Patch Extraction:** Extract complete patch bundle.
4. **Verification Workspace:** Apply patch to clean snapshot and verify.
5. **Record Ingestion:** Store run record in SQLite database.

---

## 8. Smoke → Validation → Held-Out Gating

The control loop follows strict sequential gating:
1. **Smoke Evaluation:** Fast evaluation on 1–3 targeted tasks from the failure cluster. If smoke testing fails, the candidate is immediately **REJECTED** without running large benchmarks.
2. **Validation Benchmark:** Full benchmark run on the `validation` split. Measures targeted failure mode reduction and tracks collateral category shifts.
3. **Held-Out Confirmation:** Held-out split is evaluated only when validation shows promising results. Before execution, the cryptographic `held_out.lock` is verified against the split manifest digest. Accidental repeated held-out tuning is prohibited.

---

## 9. Promotion Gate & Delta Analysis

The promotion gate (`local/fdd/gates.py`) evaluates candidate suitability:

### Criteria for PROMOTED
- Validation benchmark demonstrates measurable reduction in targeted failure mode (`targeted_reduction > 0`).
- No unacceptable collateral regressions in unrelated failure classes (`collateral_regressions <= tolerance`).
- Held-out evaluation shows no degradation compared to baseline pass rate (`held_out_regression is not True`).
- All clean-copy checks succeed and configurations remain reproducible.

### Decision Statuses
- `PROMOTED`: All gates passed with verified failure reduction.
- `REJECTED`: Target failed to decrease, smoke failed, collateral regressions occurred, or held-out degraded.
- `INCONCLUSIVE`: Results cannot establish failure reduction with sufficient statistical or observable evidence.
- `BLOCKED_INFRASTRUCTURE`: Evaluation blocked by environment limits.
- `NO_ACTIONABLE_DATA`: Zero actionable completed failure runs available.

---

## 10. Reproducibility and Manifests

Every experiment produces a permanent audit directory in `experiments/fdd/<intervention-id>/`:
- `manifest.json`: Experiment metadata, execution state, and SHA-256 hashes of all artifacts.
- `intervention.json`: Complete typed intervention specification.
- `cluster.json`: Root failure cluster snapshot.
- `result.json`: Quantitative delta measurements and decision rationale.
- `report.md`: Human-readable markdown audit report.
- Subdirectories `smoke/`, `validation/`, `held_out/`: Exact normalized run records.

---

## 11. Command-Line Interface

The FDD loop provides a composable CLI (`scripts/run_fdd.py`):

```bash
# Analyze candidate failures and evidence modes
python scripts/run_fdd.py --candidate E0 --split dev --analyze

# Deterministically cluster candidate failures
python scripts/run_fdd.py --candidate E0 --split dev --cluster

# Select highest-value failure cluster
python scripts/run_fdd.py --candidate E0 --split dev --select

# Verify cryptographic integrity of experiment artifacts
python scripts/run_fdd.py --verify experiments/fdd/<intervention-id>
```

---

## 12. Current Scope and Non-Goals

- **No Prompt Optimization:** Stage 32 will perform prompt refinement using this harness.
- **No Retrieval Optimization:** Stage 33 will address retrieval heuristics.
- **No LoRA Training:** Stage 37+ will handle model fine-tuning.
- **No Leaderboard Gaming:** Optimization is guided strictly by empirical failure reduction.
