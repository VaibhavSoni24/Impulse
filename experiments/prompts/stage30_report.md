# Stage 30 Execution Report: Failure Dashboard & Evaluation Reporting

## 1. Status
COMPLETE, FROZEN, AND VERIFIED

## 2. Parent Commit
`5c45f53f3321c4e7ea987eda43b43809f8d2f73a` (Stage 29 Complete, Frozen, and Verified)

## 3. Current Commit
`42b452987ba463d0771b5ec11c6ada362d7b4b0b`

## 4. Report Architecture
Implemented in `local/dashboard/` as a lightweight static report generator without web servers or interactive UIs:
- **`local/dashboard/models.py`**: Typed data models (`RunSummary`, `DashboardReport`, `MetricStats`, `RepositoryMetrics`, `TaskTypeMetrics`, `EvidenceMode`, `ReportStatus`).
- **`local/dashboard/integrity.py`**: Enforces Stage 29 split manifest verification and cryptographic `held_out.lock` tamper detection prior to report generation (`verify_split_before_dashboard`).
- **`local/dashboard/queries.py`**: Normalizes raw SQLite rows and JSONL result records into typed `RunSummary` instances, binding repository identities from the split catalog.
- **`local/dashboard/metrics.py`**: Computes overall and per-repository pass rates, continuous statistics (mean, median, p95), E9 canonical failure distributions, clean-copy evaluator stages, and recovery outcomes.
- **`local/dashboard/generator.py`**: Renders `summary.md`, `failures.jsonl`, `metrics.csv`, and `manifest.json` with Stage 27 secret scanning and SHA-256 artifact hashing.
- **`local/dashboard/cli.py` & `scripts/generate_dashboard.py`**: Command-line interfaces supporting `--candidate`, `--split`, `--verify`, `--json`, and `--mode`.

## 5. Input Data
- **SQLite Database (`experiments/evaluation.db`):** Tables `runs`, `failures`, `tasks`, `run_events`, `metrics`.
- **Baseline JSONL Runs (`experiments/baseline/E0/results.jsonl`):** 5 historical baseline evaluation runs across FastAPI, Rich, and Requests.
- **Benchmark Splits (`benchmark/splits/v1/`):** `dev.jsonl` (67 tasks), `validation.jsonl` (48 tasks), `held_out.jsonl` (14 tasks), `manifest.json`, and `held_out.lock`.
- **Source Tasks Catalog (`data/competition/tasks.jsonl`):** Authoritative competition dataset (129 tasks, 4 repositories).

## 6. Evidence Modes
Enforces strict segregation across four mutually exclusive execution regimes:
- **`LIVE`**: Competition-model inference (`gemma-4-31b-it-qat-w4a16-ct`) evaluated against clean snapshots.
- **`FIXTURE`**: Synthetic agent runs used for deterministic pipeline testing. Never combined with LIVE pass rates.
- **`INFRASTRUCTURE_ONLY`**: Execution attempts terminated before model invocation due to host environment constraints.
- **`UNAVAILABLE`**: Environment lacking required inference hardware (4x NVIDIA L4 GPUs, 96 GB VRAM). Unobserved metrics are recorded as `N/A` or empty string, never as fabricated 0.0 values.
- **`MIXED`**: Multi-mode result set preserving mode-specific breakdowns.

## 7. Generated Artifacts
Deterministic dashboard outputs generated for baseline candidate `E0`:
- **DEV Split:** [experiments/dashboard/E0/dev/](file:///e:/Projects/Impulse/experiments/dashboard/E0/dev)
  - `summary.md` (67 tasks, 2 recorded runs, status: `NO_LIVE_RESULTS`)
  - `failures.jsonl` (2 failed/unavailable runs, sorted deterministically)
  - `metrics.csv` (machine-readable standardized metrics)
  - `manifest.json` (SHA-256 bound manifest)
- **VALIDATION Split:** [experiments/dashboard/E0/validation/](file:///e:/Projects/Impulse/experiments/dashboard/E0/validation)
  - `summary.md` (48 tasks, 1 recorded run, status: `NO_LIVE_RESULTS`)
  - `failures.jsonl` (1 failed/unavailable run)
  - `metrics.csv`
  - `manifest.json`
- **HELD_OUT Split:** [experiments/dashboard/E0/held_out/](file:///e:/Projects/Impulse/experiments/dashboard/E0/held_out)
  - `summary.md` (14 tasks, 2 recorded runs, status: `NO_LIVE_RESULTS`, verified against `held_out.lock`)
  - `failures.jsonl` (2 failed/unavailable runs)
  - `metrics.csv`
  - `manifest.json`
- **ALL Splits Aggregated:** [experiments/dashboard/E0/all/](file:///e:/Projects/Impulse/experiments/dashboard/E0/all)
  - `summary.md` (129 tasks, 5 recorded runs)
  - `failures.jsonl` (5 failed/unavailable runs)
  - `metrics.csv`
  - `manifest.json`

All directories verified valid via `python scripts/generate_dashboard.py --verify`.

## 8. Metrics
- **Overall Pass Rate:** `N/A` (0 eligible completed live runs on local Windows host). Zero fabrication policy enforced.
- **Repository Breakdown:**
  - `fastapi/fastapi` (DEV): 67 tasks, 0 completed live runs, 2 unavailable runs, Pass Rate: `N/A`.
  - `Textualize/rich` (VALIDATION): 48 tasks, 0 completed live runs, 1 unavailable run, Pass Rate: `N/A`.
  - `psf/requests` (HELD_OUT): 13 tasks, 0 completed live runs, 2 unavailable runs, Pass Rate: `N/A`.
  - `encode/httpx` (HELD_OUT): 1 task, 0 completed live runs, 0 unavailable runs, Pass Rate: `N/A`.
- **Runtime:** Mean: `N/A`, Median: `N/A`, P95: `N/A`, Count: 0 completed live runs.
- **Tool Calls:** Mean: `N/A`, Median: `N/A`, P95: `N/A`, Count: 0 completed live runs.
- **Turns & Diff:** Turns: `N/A`, Patch lines: `N/A`, Files changed: `N/A`.
- **Recovery:** Triggered: 0, Successful: 0, Rate: `N/A`.

## 9. Task-Type Handling
- **Status:** `UNAVAILABLE`
- **Reason:** `source dataset does not provide task-type metadata`
- **Policy:** IMPULSE strictly adheres to empirical ground truth and does not invent speculative task categories ("bugfix", "refactor", etc.) when absent from authoritative dataset schema.

## 10. Failure Breakdown
- **Canonical E9 Categories:** 0 cognitive failures (inference was unexecuted).
- **Evaluator Pipeline / Infrastructure Stage:**
  - `INFRASTRUCTURE_UNAVAILABLE`: 5 runs (100% of recorded baseline runs).
  - Termination Reason: `Local Windows host environment lacks 4x NVIDIA L4 GPUs (96 GB VRAM) and local vLLM serving stack required to run gemma-4-31b-it-qat-w4a16-ct.`

## 11. Split Integrity
- Verified [manifest.json](file:///e:/Projects/Impulse/benchmark/splits/v1/manifest.json) integrity and hash `ddbd2baab4567cbafcdb29a3c0e131b0ae2db33abdd6c6967db3f83db6fc00e8`.
- Verified [held_out.lock](file:///e:/Projects/Impulse/benchmark/splits/v1/held_out.lock) integrity and task set hash `3d2db96fe3a30bd0f8fe122437ddd130f93d7d100ab4cb5c007450661bec240e`.
- Cross-split leakage checks confirmed 0 task overlap, 0 repo overlap, 0 commit overlap.

## 12. Focused Tests
- **Suite:** [tests/test_failure_dashboard_stage30.py](file:///e:/Projects/Impulse/tests/test_failure_dashboard_stage30.py)
- **Result:** **24 / 24 PASSED** in 1.57s

## 13. Full Regression
- **Full Discovery Suite (`python -m unittest discover tests`):** **701 / 701 PASSED** (up from 677 in Stage 29, +24 Stage 30 tests).
  - Stage 24 Topology Suite: 55 / 55 PASSED
  - Stage 25 Context Compaction Suite: 23 / 23 PASSED
  - Stage 26 Tool Budgeting Suite: 22 / 22 PASSED
  - Stage 27 Diff Discipline Suite: Post-commit clean working tree verification
  - Stage 28 Clean-Copy Evaluator Suite: 28 / 28 PASSED
  - Stage 29 Benchmark Splits Suite: 24 / 24 PASSED
  - Stage 30 Failure Dashboard Suite: 24 / 24 PASSED

## 14. Submission Validation
All candidates passed official competition submission validation:
- Candidate M0: `PASSED` (0.03 MB, single model `gemma-4-31b-it-qat-w4a16-ct`)
- Candidate M1: `PASSED` (0.03 MB, single model `gemma-4-31b-it-qat-w4a16-ct`)
- Candidate M2: `PASSED` (0.03 MB, single model `gemma-4-31b-it-qat-w4a16-ct`)
- Candidate M3: `PASSED` (0.03 MB, single model `gemma-4-31b-it-qat-w4a16-ct`)
- Candidate M4: `PASSED` (0.03 MB, single model `gemma-4-31b-it-qat-w4a16-ct`)
- Candidate M5: `PASSED` (0.04 MB, single model `gemma-4-31b-it-qat-w4a16-ct`)

## 15. Frozen Artifact Verification
All 9 authoritative Stage 24 artifacts verified invariant:
- Scout YAML (`335c1a32...`): `MATCH`
- Scout prompt (`d57f433c...`): `MATCH`
- Debugger YAML (`07b936c8...`): `MATCH`
- Debugger prompt (`a743a30b...`): `MATCH`
- Reviewer YAML (`facfcbb4...`): `MATCH`
- Reviewer prompt (`d2432da5...`): `MATCH`
- Shared topology root prompt (`2360d4bf...`): `MATCH`
- Test strategy skill (`3d027b0f...`): `MATCH`
- Repo triage skill (`ac7a9671...`): `MATCH`

## 16. Real vs Fixture Evidence
- **Real Evidence:** Baseline E0 dashboard reports generated directly from recorded baseline runs in `experiments/baseline/E0/results.jsonl`, reflecting the actual host availability constraint.
- **Fixture Evidence:** Tested in temporary directories across all-pass, all-fail, recovery, and clean-copy verification scenarios in `test_failure_dashboard_stage30.py`. Fixture results are explicitly tagged with `evidence_mode: FIXTURE` and never pollute production benchmark reports.

## 17. Known Limitations
- Live Gemma 4 31B competition inference remains unavailable on the local Windows host environment (requires 4x NVIDIA L4 GPUs, 96 GB VRAM).
- Candidates M0 through M5 currently have zero live runs recorded on this host; their reports correctly reflect `NO_RESULTS` with null pass rates. No topology winner is declared.

## 18. Stage 31+ Confirmation
- Stage 31 (Failure-Driven Development Loop) is **NOT** implemented.
- Stage 32+ (Optimization Loops) is **NOT** implemented.
- LoRA Fine-Tuning is **NOT** implemented.

## 19. Final Git Status
Working tree clean after atomic Stage 30 commit.
