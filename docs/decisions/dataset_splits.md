# Architecture Decision Record: Reproducible Benchmark Dataset Splits (Stage 29)

- **Status:** ACCEPTED & FROZEN
- **Date:** 2026-09-29
- **Parent Stage:** Stage 28 (Clean-Copy Local Evaluator)
- **Authoritative Plan Reference:** PLAN.md Stage 29
- **Primary Objective:** Partition the actual competition development dataset into reproducible, leakage-free DEV, VALIDATION, and HELD_OUT splits protected by cryptographic manifests and lockfiles.

---

## 1. Context and Problem Statement

To evaluate autonomous software engineering agents objectively, benchmark evaluation requires strict data partitioning:
1. **DEV**: Broad exploratory work, prompt iteration, retrieval tuning, and smoke testing.
2. **VALIDATION**: Controlled candidate comparison (`M0` through `M5`), promotion decisions, and hyperparameter tuning.
3. **HELD_OUT**: Final validation and confirmation. Must remain strictly untouched during iterative development and prompt engineering.

In repository-level SWE benchmarks (such as SWE-bench and the Google Gemma 4 Developer Agent Competition), tasks belong to real open-source repositories. A naive random row-level split causes severe **data leakage**:
- If tasks from the same repository appear across DEV and HELD_OUT, the agent can overfit to repository architecture, directory layouts, and coding conventions learned in DEV.
- If tasks from the same commit snapshot appear in different splits, the agent may encounter identical repository trees.
- If identical or near-duplicate problem statements cross splits, test outcomes are compromised.

Stage 29 designs and implements an authoritative, reproducible benchmark splitting subsystem that enforces group-level isolation and cryptographic immutability.

---

## 2. Source Dataset Audit

The competition development dataset was located and validated:
- **Location:** `data/competition/tasks.jsonl`
- **Availability Status:** `AVAILABLE`
- **Total Records:** 129
- **Source SHA-256:** `e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6`
- **Unique Repositories:** 4
  - `fastapi/fastapi`: 67 tasks (51.94%)
  - `Textualize/rich`: 48 tasks (37.21%)
  - `psf/requests`: 13 tasks (10.08%)
  - `encode/httpx`: 1 task (0.78%)
- **Unique Base Commits:** 127
- **Commit Overlap:** Exactly 2 commits contain 2 tasks each (`Textualize/rich` @ `4d6d631a3d`, `psf/requests` @ `7a13c041db`); all other 125 commits are unique.

---

## 3. Split Roles and Boundaries

| Split | Purpose | Rules & Constraints |
|---|---|---|
| **DEV** | Routine development, prompt engineering, retrieval tuning, smoke verification | May be run repeatedly during development iterations. |
| **VALIDATION** | Candidate comparison (`M0`–`M5`), component ablation, promotion decisions | Run selectively to compare frozen candidates; not for continuous inner-loop debugging. |
| **HELD_OUT** | Final confirmation of promoted candidates | **PROTECTED & LOCKED.** Never used for prompt tuning or debugging. Locked by `held_out.lock`. |

---

## 4. Grouping & Allocation Policy

### 4.1 Primary Policy: `REPO_DISJOINT`
Given 4 repositories and 129 tasks, group-level repository isolation is achievable:
- **DEV**: `fastapi/fastapi` (67 tasks, 51.94%)
- **VALIDATION**: `Textualize/rich` (48 tasks, 37.21%)
- **HELD_OUT**: `psf/requests` (13 tasks) + `encode/httpx` (1 task) (14 tasks, 10.85%)

**Benefits:**
- **Zero Cross-Split Repository Leakage:** 0% repository overlap across all split pairs.
- **Zero Commit Leakage:** 0% commit snapshot overlap.
- **True Generalization Test:** Evaluating on VALIDATION or HELD_OUT measures generalization to completely unseen codebases.

### 4.2 Alternative Policy: `STRATIFIED_COMMIT_ISOLATED`
For scenarios requiring multi-repo representation in DEV and VALIDATION:
- Clustered by `(repo, base_commit)` to ensure tasks sharing a commit snapshot never cross splits.
- Deterministically hashes cluster keys into target proportion buckets.

---

## 5. Duplicate and Exclusion Handling

1. **Exact Duplicate IDs:** Detected in `load_and_validate_source`. Duplicate records are quarantined into `exclusions.json` under policy rule `SOURCE_DUPLICATE_REJECTION`.
2. **Problem Statement Duplication:** `validate_split_leakage` checks for identical problem statements across splits.
3. **Malformed Records:** Missing required fields (`instance_id`, `repo`, `base_commit`) or invalid JSON syntax are quarantined into `exclusions.json`.
4. **Canonical V1 Status:** In `data/competition/tasks.jsonl`, all 129 records are structurally valid and unique. 0 exclusions.

---

## 6. Deterministic Generation & Hashing

Split generation is 100% deterministic and byte-identical across runs:
1. **Source Sorting:** Tasks sorted canonically by `(repo, base_commit, instance_id)`.
2. **Canonical Task-Set Hashing:** `compute_canonical_task_set_hash` computes SHA-256 over sorted, compact JSON representations of `(instance_id, repo, base_commit, problem_statement)` tuples.
3. **File Hashing:** SHA-256 of generated `.jsonl` files.
4. **Manifest Hashing:** `compute_manifest_sha256` computes SHA-256 over all fields of `manifest.json` (excluding `manifest_sha256` itself) using sorted keys.

---

## 7. Cross-Split Leakage Validation

Implemented in `benchmark/splits/leakage.py` (`validate_split_leakage`):
1. **Internal Uniqueness:** Task IDs unique within each split.
2. **Cross-Split Task Disjointness:** No task ID exists in more than one split.
3. **No Duplicate Text Across Splits:** No identical problem statements cross splits.
4. **Repository Isolation:** When using `REPO_DISJOINT`, pairwise intersection of repositories is empty.
5. **Commit Snapshot Isolation:** No tasks sharing a `base_commit` cross splits.
6. **Source Fidelity:** Split tasks exist verbatim in source dataset.
7. **Accounting Completeness:** Sum of split tasks + exclusions exactly equals source record count.

---

## 8. Held-Out Protection & Lockfile

Implemented in `benchmark/splits/held_out_lock.py`:
- `held_out.lock` stores:
  - `held_out_count`
  - `held_out_tasks` (sorted list of task IDs)
  - `task_set_sha256`
  - `held_out_file_sha256`
  - `manifest_sha256`
- **Safeguards:**
  - `is_held_out_task(task_id, lock_path)` allows runners to check if a task is protected before running.
  - `verify_held_out_lock` verifies that held-out tasks and file hashes have not been tampered with or silently altered.

---

## 9. Source Versioning & Regeneration Safety

1. **Source Change Detection:** `detect_source_change` compares `source_sha256` in `manifest.json` with the current hash of the source file. If modified, split reuse is rejected.
2. **Regeneration Safety:** `SplitGenerator.generate(force=False)` raises `FileExistsError` if the output directory already contains splits. Overwrite requires explicit `--force`.
3. **Versioned Directories:** Splits are written to versioned paths (`benchmark/splits/v1/`, `v2/`, etc.).

---

## 10. Stage 28 Integration

The Stage 28 Clean-Copy Evaluator and runner were extended to consume split artifacts:
- `TaskLoader.from_split(split_name, split_version, splits_root)`: Loads tasks directly from split files (`dev.jsonl`, `validation.jsonl`, `held_out.jsonl`).
- `CleanCopyEvaluator.evaluate_task`: Accepts `split_name`, `split_version`, and `split_manifest_sha256`.
- `local/evaluation/schema.py`: Database schema records `split_name`, `split_version`, and `split_manifest_sha256` on every evaluation run.
- `scripts/clean_copy_eval.py`: Accepts `--split [dev|validation|held_out]` CLI argument.

---

## 11. Limitations and Non-Goals

- **Small Repository Universe:** The competition dataset contains 4 repositories. While 129 tasks provide solid coverage, repository-level stratification is coarse (DEV: 1 repo, VALIDATION: 1 repo, HELD_OUT: 2 repos).
- **Stage 30+ Non-Goals:** Stage 29 does NOT implement failure dashboards (Stage 30), failure-driven optimization loops (Stage 31), prompt optimization (Stage 32), or LoRA fine-tuning.
