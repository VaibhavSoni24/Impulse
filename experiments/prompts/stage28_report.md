# Stage 28 Execution Report: Clean-Copy Evaluator

## 1. Status
COMPLETE, FROZEN, AND VERIFIED

## 2. Parent Commit
`ffc4cd1a03c4808b9cca008dab5ad40687005439` (Stage 27 Complete, Frozen, and Verified)

## 3. Current Commit
`f85822a151093ab023a20eb73fb8d55107e862fe`

## 4. Architecture
Existing runner and evaluation subsystems reused and extended:
- **`local/runner/`**: Extended `cli.py` to support `--clean-copy`, `--mode [fixture|live|unavailable]`, and `--baseline-commit`. Retained `task_loader.py` and existing task specifications.
- **`local/evaluation/`**: Extended database schema (`schema.py`), query layer (`queries.py`), and record ingestion (`ingestion.py`) in SQLite store (`eval.db`), adding clean-copy verification fields while guaranteeing backward compatibility with Stage 5-9 historical runs via idempotent column migration.
- **`local/diff_discipline/`**: Integrated Stage 27 secret detection (`scan_content_for_secrets`) and frozen artifact verification (`verify_frozen_artifacts`) into patch validation boundaries.
- **`local/context_compaction/`**: Reused Stage 25 path normalization (`normalize_path`) and SHA-256 fingerprinting (`compute_content_sha256`).
- **`local/budgeting/`**: Reused tool-call budgeting schemas, ensuring execution tool events remain correctly bound to unique evaluation `run_id`s.

## 5. Clean Snapshot
Implemented in `local/clean_copy/snapshot.py`:
- **`CleanRepositorySnapshot`**: Hermetic task snapshot possessing:
  - Baseline commit SHA identity.
  - Dedicated isolated filesystem location outside main project workspace.
  - Verification of initial Git cleanliness via `git status --short`.
  - Configured Git exclude rules (`core.excludesFile`) ensuring standard build/cache artifacts (`__pycache__`, `.pytest_cache`, `.coverage`) are ignored without modifying repository configuration.
- **`SnapshotManager`**:
  - Validates baseline repository cleanliness (rejects dirty developer repositories unless `--allow-dirty-baseline` is explicitly specified).
  - Primary creation: `git worktree add --detach <path> <commit_sha>`.
  - Fallback creation: `git clone --shared --no-checkout` + `git checkout <commit_sha>`.
  - Deterministic Windows permission cleanup handler (`_remove_readonly`).

## 6. Candidate Loading
Implemented in `local/clean_copy/candidate_loader.py`:
- Deterministically resolves candidate references (`M0` through `M5` or direct paths).
- Structural validation using official competition `SubmissionValidator`.
- Cryptographic SHA-256 verification of `agent.yaml`, prompts, and full candidate package.
- Materializes candidate configuration into execution environments without mutating source candidate packages.

## 7. Agent Execution
Implemented in `local/clean_copy/adapter.py`:
- **`FIXTURE`**: Synthetic agent for deterministic end-to-end evaluator testing.
- **`LIVE`**: Execution boundary for the competition model (`gemma-4-31b-it-qat-w4a16-ct`).
- **`UNAVAILABLE`**: Explicit status returned when required inference runtime (4x NVIDIA L4 GPUs, 96 GB VRAM, vLLM serving stack) is absent on the local Windows host. Never fabricates results or silently downgrades.

## 8. Patch Extraction
Implemented in `local/clean_copy/patch_extractor.py`:
- Follows competition patch capture sequence:
  1. `git add -N .` (stages untracked intent while respecting excludes).
  2. `git diff HEAD` (captures unified diff including file additions, deletions, modifications).
  3. `git diff --name-status HEAD` (classifies added, deleted, and modified paths).
- Validates patch security boundaries:
  - Rejects directory traversal (`../`) and absolute external paths.
  - Scans patch content and new files for credentials and secrets.
  - Rejects evaluator internals or temporary files.
- Generates reproducible `PatchBundle`.

## 9. Fresh Patch Application
Implemented in `local/clean_copy/patch_applier.py`:
- Materializes a completely separate, clean validation repository snapshot at the identical baseline commit.
- Applies `PatchBundle` using `git apply --whitespace=nowarn`.
- Detects conflicts and classifies as `PATCH_APPLY_CONFLICT`.
- Validates expected file creations and deletions.

## 10. Patch Equivalence
Implemented in `local/clean_copy/equivalence.py`:
- Compares agent workspace files against applied validation workspace files.
- Evaluates semantic SHA-256 file content equivalence across changed paths.

## 11. Verification
Implemented in `local/clean_copy/verifier.py`:
- Executes task verification commands strictly inside the clean validation workspace.
- Records command line, return code, stdout, stderr, execution duration, and pass/fail status.

## 12. Isolation
- **Multi-Task Isolation**: Tested in `test_18_multi_task_workspace_isolation`. Task A's filesystem changes do not leak to Task B.
- **Candidate Isolation**: Tested in `test_19_candidate_isolation`. Candidate configurations are immutable and isolated.

## 13. Focused Tests
`tests/test_clean_copy_evaluator_stage28.py`:
- **28 / 28 passed** (100% pass rate in 15.65s).
- Covers all required test sections A through N.

## 14. Full Regression Suite
- Total test count: **653 tests**
- Execution: `python -m unittest discover tests`
- All unit, integration, and stage-specific tests passing.

## 15. Submission Validation
Executed `python scripts/validate_submission.py` across all candidates:
- `experiments/candidates/M0`: PASS
- `experiments/candidates/M1`: PASS
- `experiments/candidates/M2`: PASS
- `experiments/candidates/M3`: PASS
- `experiments/candidates/M4`: PASS
- `experiments/candidates/M5`: PASS

## 16. Frozen Artifact Verification
Authoritative hashes verified via `local.diff_discipline.frozen_verifier.verify_frozen_artifacts`:
- `agent/sub_agents/scout.yaml`: MATCH (`335c1a32...`)
- `agent/prompts/scout.md`: MATCH (`d57f433c...`)
- `agent/sub_agents/debugger.yaml`: MATCH (`07b936c8...`)
- `agent/prompts/debugger.md`: MATCH (`a743a30b...`)
- `agent/sub_agents/reviewer.yaml`: MATCH (`facfcbb4...`)
- `agent/prompts/reviewer.md`: MATCH (`d2432da5...`)
- `experiments/candidates/M0-M5/prompts/root.md`: MATCH (`2360d4bf...`)
- `agent/skills/test_strategy/SKILL.md`: MATCH (`3d027b0f...`)
- `agent/skills/repo_triage/SKILL.md`: MATCH (`ac7a9671...`)

## 17. Real vs Fixture Evidence
- **Fixture Evidence**: End-to-end evaluation demonstrated via `CleanCopyEvaluator` with synthetic and fixture agents. Successfully validates patch extraction, clean-copy application, and verification.
- **Critical Regression**: Verified in `test_16_critical_regression_dirty_workspace_pass_clean_copy_fail`. When a task passes in dirty workspace due to untracked/disposable side-effects but fails in clean copy, the evaluation is marked as `FAILED`.

## 18. Competition Metrics
Live model execution on the local host is explicitly recorded as `UNAVAILABLE`:
- Reason: Local host lacks required GPU hardware (4x NVIDIA L4 GPUs, 96 GB VRAM) and vLLM inference server.
- No live benchmark numbers or pass rates were fabricated.

## 19. Known Limitations
- Windows file locking requires robust retry/read-only permission removal during worktree disposal.
- Live model evaluation requires remote execution on a Kaggle container or dedicated GPU instance.

## 20. Stage 29+ Confirmation
- Stage 29 (Dataset Split Construction): NOT implemented.
- Stage 30 (Dashboard & Evaluation Reporting): NOT implemented.
- LoRA Fine-Tuning: NOT implemented.

## 21. Final Git Status
Working tree contains only Stage 28 implementation, test suite, ADR, and report.

STAGE 28 COMPLETE, FROZEN, AND VERIFIED
