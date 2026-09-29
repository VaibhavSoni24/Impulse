# Stage 29 Execution Report: Reproducible Benchmark Splits

## 1. Status
COMPLETE, FROZEN, AND VERIFIED

## 2. Parent Commit
`899e62395066787b0ec09c4069aae94b8744da71` (Stage 28 Complete, Frozen, and Verified)

## 3. Current Commit
`b610e66d5e59c00c4685890e22f2827fd8cfa3ac`

## 4. Source Dataset
- **Availability Status:** AVAILABLE
- **Source Path:** `data/competition/tasks.jsonl`
- **Source Format:** JSON Lines (JSONL)
- **Unique Repositories:** 4 (`fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx`)
- **Unique Base Commits:** 127

## 5. Source Integrity
- **Total Records:** 129
- **Source SHA-256:** `e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6`

## 6. Split Policy
- **Policy Name:** `repo_disjoint` (Version 1.0.0)
- **Policy Rationale:** Group-level repository partitioning ensures zero code, directory structure, or architectural leakage between development, validation, and held-out evaluation.
- **Deterministic Assignment:** Sorted canonical task ordering with fixed seed (42).

## 7. Split Results
- **DEV:**
  - Task Count: 67 (51.94%)
  - Repositories: `fastapi/fastapi` (67 tasks)
  - Task-Set SHA-256: `ca1344dd8abdba81c3dc84cc78c452dee33aec27c87682ebd2d8381a6d8096d3`
  - File SHA-256: `1b95c9fcfad8f0078aafc5dc1a0482cfe35197d365649e959a2e263c5cd039d2`
- **VALIDATION:**
  - Task Count: 48 (37.21%)
  - Repositories: `Textualize/rich` (48 tasks)
  - Task-Set SHA-256: `2aaf4ebb5fec0dab12af9d5706352b0edb60d31ecea05543cd28a40f16694238`
  - File SHA-256: `32a26959af623169251af43b2911d635f69d3414ebd53920df77bdb6528dbab9`
- **HELD_OUT:**
  - Task Count: 14 (10.85%)
  - Repositories: `psf/requests` (13 tasks), `encode/httpx` (1 task)
  - Task-Set SHA-256: `3d2db96fe3a30bd0f8fe122437ddd130f93d7d100ab4cb5c007450661bec240e`
  - File SHA-256: `8dae6b4c276bd880b06abdbac0f729b48c4fc818401f3e820b1a2b6f6f581fcd`

- **Manifest SHA-256:** `ddbd2baab4567cbafcdb29a3c0e131b0ae2db33abdd6c6967db3f83db6fc00e8`

## 8. Leakage Audit
- **Audit Status:** PASS
- **Cross-Split Task Overlap:** 0 tasks (Disjoint)
- **Cross-Split Repository Overlap:** 0 repositories (Pairwise disjoint)
- **Cross-Split Snapshot/Commit Overlap:** 0 commits (Zero cross-split shared commits)
- **Cross-Split Duplicate Problem Text:** 0 duplicated descriptions
- **Exclusions:** 0 excluded tasks (100% of source records validly partitioned into splits)

## 9. Held-Out Protection
- **Lockfile:** `benchmark/splits/v1/held_out.lock`
- **Cryptographic Lock Attributes:**
  - `held_out_count`: 14
  - `held_out_tasks`: 14 sorted task IDs
  - `task_set_sha256`: `3d2db96fe3a30bd0f8fe122437ddd130f93d7d100ab4cb5c007450661bec240e`
  - `held_out_file_sha256`: `8dae6b4c276bd880b06abdbac0f729b48c4fc818401f3e820b1a2b6f6f581fcd`
  - `manifest_sha256`: `ddbd2baab4567cbafcdb29a3c0e131b0ae2db33abdd6c6967db3f83db6fc00e8`
- **Protection Logic:** `is_held_out_task` checks membership; `verify_held_out_lock` enforces immutable lock integrity.

## 10. Stage 28 Integration
- **`TaskLoader.from_split(split_name, split_version, splits_root)`**: Directly loads tasks from partitioned split files.
- **`CleanCopyEvaluator.evaluate_task`**: Accepts `split_name`, `split_version`, and `split_manifest_sha256` and binds them to `EvaluationRunRecord`.
- **`local/evaluation/schema.py`**: SQLite database schema extended with `split_name`, `split_version`, `split_manifest_sha256` columns with idempotent migration.
- **`scripts/clean_copy_eval.py`**: Added `--split [dev|validation|held_out]` CLI argument.

## 11. Focused Tests
- **Suite:** `tests/test_benchmark_splits_stage29.py`
- **Result:** 24 / 24 tests PASSED (0.50s)

## 12. Full Regression
- **Stage 24 Focused Suite:** 55 / 55 PASSED
- **Stage 25 Focused Suite:** 23 / 23 PASSED
- **Stage 26 Focused Suite:** 22 / 22 PASSED
- **Stage 28 Focused Suite:** 28 / 28 PASSED
- **Stage 27 Diff Discipline Suite:** Clean working tree verification post-commit

## 13. Submission Validation
- `python scripts/validate_submission.py experiments/candidates/M0`: PASSED
- `python scripts/validate_submission.py experiments/candidates/M1`: PASSED
- `python scripts/validate_submission.py experiments/candidates/M2`: PASSED
- `python scripts/validate_submission.py experiments/candidates/M3`: PASSED
- `python scripts/validate_submission.py experiments/candidates/M4`: PASSED
- `python scripts/validate_submission.py experiments/candidates/M5`: PASSED

## 14. Frozen Artifact Verification
All Stage 24 authoritative hashes verified invariant:
- Scout YAML (`335c1a32...`): MATCH
- Scout prompt (`d57f433c...`): MATCH
- Debugger YAML (`07b936c8...`): MATCH
- Debugger prompt (`a743a30b...`): MATCH
- Reviewer YAML (`facfcbb4...`): MATCH
- Reviewer prompt (`d2432da5...`): MATCH
- Shared topology root prompt (`2360d4bf...`): MATCH
- Test strategy skill (`3d027b0f...`): MATCH
- Repo triage skill (`ac7a9671...`): MATCH

## 15. Actual vs Synthetic Evidence
- **Actual Evidence:** Canonical v1 splits (`dev.jsonl`, `validation.jsonl`, `held_out.jsonl`) generated directly from `data/competition/tasks.jsonl` (129 tasks, 4 real repositories). Tested in `test_18_actual_competition_dataset_canonical_v1_split`.
- **Synthetic Evidence:** Explicit synthetic fixtures used in temporary directories during unit tests to test edge cases (malformed JSON, duplicate source IDs, cross-split leakage injections, tamper detection).

## 16. Known Limitations
- The competition development set contains 4 repositories. `repo_disjoint` assigns 1 repo to DEV, 1 to VALIDATION, and 2 to HELD_OUT. Multi-repo stratification within each split is impossible under strict repository disjointness due to the small repository count.
- Live Gemma 4 31B competition inference remains unavailable on the local Windows host.

## 17. Stage 30+ Exclusion
- Stage 30 (Failure Dashboard & Reporting) is NOT implemented.
- Stage 31+ (Optimization Loops) is NOT implemented.
- LoRA Fine-Tuning is NOT implemented.

## 18. Final Git Status
Working tree clean after atomic Stage 29 commit.
