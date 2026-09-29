# Architecture Decision Record: Lightweight Failure Dashboard & Evaluation Reporting (Stage 30)

- **Status:** ACCEPTED & FROZEN
- **Date:** 2026-09-29
- **Parent Stage:** Stage 29 (Reproducible Benchmark Dataset Splits)
- **Authoritative Plan Reference:** PLAN.md Stage 30
- **Primary Objective:** Establish a lightweight, deterministic report generation subsystem producing `summary.md`, `failures.jsonl`, `metrics.csv`, and `manifest.json` per candidate and split without building web applications, servers, or interactive dashboards.

---

## 1. Context and Problem Statement

Following the construction of the Stage 28 Clean-Copy Evaluator and Stage 29 reproducible benchmark splits (`DEV`, `VALIDATION`, `HELD_OUT`), evaluation runs generate structured outcomes stored across SQLite (`runs`, `failures`, `tasks`), JSONL result files, and clean-copy run records.

To prepare for iterative improvement (Stage 31+), researchers and engineers require structured visibility into:
1. Overall and per-repository pass rates;
2. Canonical failure categories (E9 taxonomy) and clean-copy evaluator infrastructure stages;
3. Execution runtime, tool call volume, turn efficiency, and recovery path outcomes;
4. Machine-readable failure extraction for downstream analysis.

Building a heavy web app (e.g. Streamlit, React, FastAPI dashboard) introduces severe dependency sprawl, stateful server vulnerabilities, and breaks headless CLI reproducibility. Stage 30 fulfills this requirement strictly via a **lightweight Python report generator** producing static, versioned, cryptographic markdown, JSONL, and CSV artifacts.

---

## 2. Architectural Design & Subsystems

The dashboard architecture consists of four modular components in `local/dashboard/`:

```
┌────────────────────────────────────────────────────────┐
│                   Evaluation Sources                   │
│   (SQLite eval.db, results.jsonl, benchmark splits)    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             Split Integrity & Held-Out Safety          │
│              (local/dashboard/integrity.py)            │
│  - Verifies Stage 29 split manifest hashes             │
│  - Verifies held_out.lock cryptographic integrity      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              Data Query & Normalization Engine         │
│               (local/dashboard/queries.py)             │
│  - Normalizes raw records into typed RunSummary        │
│  - Resolves repository mapping & task catalogs         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              Deterministic Metric Calculator           │
│               (local/dashboard/metrics.py)             │
│  - Overall & per-repository pass rates                 │
│  - Continuous statistics (mean, median, p95)           │
│  - Canonical E9 failure classification                 │
│  - Evaluator clean-copy stage aggregation              │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              Report Artifact Generator & CLI           │
│        (local/dashboard/generator.py & cli.py)         │
│  - experiments/dashboard/<candidate>/<split>/          │
│      ├── summary.md                                    │
│      ├── failures.jsonl                                │
│      ├── metrics.csv                                   │
│      └── manifest.json                                 │
└────────────────────────────────────────────────────────┘
```

---

## 3. Evidence Modes & Zero Fabrication

To prevent synthetic testing from contaminating official competition evaluation, four mutually exclusive evidence modes are enforced:

| Mode | Definition | Eligibility Rule |
|---|---|---|
| **LIVE** | Real execution with Gemma 4 31B and official evaluation harness. | Only completed live inference runs count toward official pass rates. |
| **FIXTURE** | Synthetic agent execution used for deterministic pipeline testing. | Strictly isolated; never combined with LIVE metrics. |
| **INFRASTRUCTURE_ONLY** | Host/hardware failures occurring prior to model inference. | Reported as infrastructure availability limits, not agent errors. |
| **UNAVAILABLE** | Execution was unattempted due to missing local inference stack. | Metric values reported as `N/A` or empty, never fabricated as `0.0`. |
| **MIXED** | Multi-mode result set. | Explicitly distinguishes mode counts and preserves separation. |

### Null / Unavailable Policy
- **Zero Fabrication Principle:** If a quantity is unobserved (e.g. tool calls on an unexecuted run, or pass rate with zero completed runs), it is recorded as `None` (JSON/Python), `""` (CSV), and `N/A` (Markdown).
- Under no circumstances is an unexecuted run recorded as a `0%` pass rate.

---

## 4. Task-Type Handling & Dataset Limitations

Inspection of the competition dataset (`data/competition/tasks.jsonl`) confirms that canonical fields consist of:
`instance_id`, `repo`, `base_commit`, `problem_statement`, `hints_text`, `created_at`, `patch`, `test_patch`.

**Decision:**
- IMPULSE does **NOT** invent speculative task categories (such as "bugfix", "multi-file", or "feature").
- The task-type section of `summary.md` and `metrics.csv` explicitly reports:
  - **Status:** `UNAVAILABLE`
  - **Reason:** `source dataset does not provide task-type metadata`
- If future benchmark releases include authoritative category labels, the schema automatically binds them without retroactive fabrication.

---

## 5. Failure Taxonomy: E9 Canonical vs Evaluator Stages

The dashboard cleanly segregates agent-level cognitive failures from evaluation infrastructure failures:

### 5.1 Canonical E9 Failure Classes
1. `ENVIRONMENT`: Setup, dependency, or runtime environment issues.
2. `COMMAND`: Shell syntax, missing binaries, or command invocation errors.
3. `PRE_EXISTING_FAILURE`: Test was already failing prior to patch application.
4. `REGRESSION`: Patch caused previously passing tests to fail.
5. `INCOMPLETE_FIX`: Patch addresses part of the problem but fails remaining assertions.
6. `WRONG_HYPOTHESIS`: Patch implements an incorrect solution approach.
7. `NEW_EDGE_CASE`: Patch exposes unexpected boundary condition.
8. `UNKNOWN`: Unclassified cognitive failure.

### 5.2 Evaluator Clean-Copy Infrastructure Stages
- `PATCH_APPLY_CONFLICT`: Git patch could not be applied cleanly to a clean copy.
- `PATCH_EXTRACTION_FAILURE`: Failed to extract unified diff from agent workspace.
- `RUNTIME_UNAVAILABLE`: Local host lacked required GPU/serving infrastructure.
- `VERIFICATION_COMMAND_FAILURE`: Test runner execution crashed or timed out.
- `CLEANUP_FAILURE`: Temporary snapshot disposal failure.

Pipeline failures are reported in a distinct table to ensure infrastructure issues do not distort model reasoning metrics.

---

## 6. Output Artifacts & Formats

Generated under `experiments/dashboard/<candidate>/<split>/`:

1. **`summary.md`**: Human-readable Markdown summary containing metadata, dataset totals, pass rate tables by repository and task type, failure category distributions, runtime percentiles, tool call stats, and recovery performance.
2. **`failures.jsonl`**: Machine-readable JSON lines file containing one record per failed or unexecuted run, deterministically sorted by `(split, candidate_id, task_id, run_id)`.
3. **`metrics.csv`**: Standard machine-readable CSV table containing 26 standardized columns with empty string representations for unobserved values.
4. **`manifest.json`**: Cryptographic reproducibility record binding generator version, Git commit SHA, candidate ID, split manifest SHA-256, source database SHA-256, record counts, and SHA-256 hashes of all three companion artifacts.

---

## 7. Split Integrity & Held-Out Safety

Prior to generating reports:
- `verify_split_before_dashboard` validates the integrity of the Stage 29 split manifest (`benchmark/splits/v1/manifest.json`).
- If `split == "held_out"`, `verify_held_out_lock` verifies that `held_out.lock` matches the frozen manifest and has not been tampered with.
- If any check fails, generation is immediately aborted with `SplitIntegrityError`.
- The dashboard generator is strictly read-only with respect to benchmark splits: it never alters `held_out.lock`, mutates split files, or tunes parameters on held-out tasks.

---

## 8. Security & Repository Hygiene

- **Secret Scanning:** All rendered text artifacts (`summary.md`, `failures.jsonl`) are scanned using `scan_content_for_secrets` prior to disk write. Any credential or API token match raises an exception.
- **Path Hygiene:** No absolute developer home paths (e.g. `C:/Users/...`) are persisted; all references use relative repository paths or opaque IDs.
- **Log Bounding:** Full raw tracebacks and massive stdout streams are omitted from `failures.jsonl` to prevent TaskState bloat.

---

## 9. Non-Goals & Boundaries

- **No Web Application:** No Flask, FastAPI, Streamlit, or React applications were created.
- **No Optimization Loops (Stage 31+):** Stage 30 strictly reports evidence; it does not select failures for remediation, optimize prompts, tune retrieval, or run LoRA training.
- **No Topology Selection:** Stage 30 does NOT declare a winning topology among candidates `M0` through `M5`.
