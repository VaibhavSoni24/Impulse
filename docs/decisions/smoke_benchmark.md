# Smoke Benchmark Set Selection & Audit — IMPULSE

This document records the selection rationale, category taxonomy, and experimental boundaries for the initial 5-task smoke benchmark set (`benchmark/tasks/smoke.jsonl`), established in **Stage 6** of `PLAN.md`.

---

## 1. Purpose & Experimental Role

The smoke benchmark set is a compact, diverse 5-task slice selected from the official competition development manifest.

### What the Smoke Set IS:
- **Plumbing Verification:** Ensures that candidate agents compile, load tasks, invoke tools, and emit structured outputs without infrastructure crashes.
- **Regression Testing:** Verifies that agent updates or refactorings do not cause fundamental pipeline regressions.
- **Rapid Sanity Checking:** Provides a lightweight sanity check before deploying long-running full-benchmark runs.

### What the Smoke Set IS NOT:
- **NOT** the full development benchmark (which comprises 129 tasks in `data/competition/tasks.jsonl`).
- **NOT** a validation split or held-out test set.
- **NOT** evidence of `IMPULSE-E0` benchmark performance (no evaluation runs have been performed).
- **NOT** a proxy for the Kaggle leaderboard score.
- **STRICT PROHIBITION:** Candidates must **never** be hard-coded, over-fitted, or heuristically tuned against these specific 5 tasks.

---

## 2. Source Dataset & Selection Methodology

- **Source Manifest:** `data/competition/tasks.jsonl`
- **Total Source Tasks:** 129 tasks across 4 repositories (`fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx`).
- **Data Integrity Protocol (Strict Zero-Leakage):**
  - The golden solution patch (`patch`) and official test patch (`test_patch`) were **NOT** inspected or used in any way to select tasks or assess difficulty.
  - Task selection was grounded strictly on information legitimately available prior to solving the task: `instance_id`, `repo`, `base_commit`, `problem_statement`, and `hints_text`.

---

## 3. Selected Task Portfolio

| # | Task ID | Repository | Category | Base Commit | Primary Evidence / Rationale |
|---|---|---|---|---|---|
| 1 | **`fastapi_14786`** | `fastapi/fastapi` | `easy_localization` | `eacbce24` | Narrow problem statement explicitly identifying target function `get_authorization_scheme_param()` in `fastapi/security/utils.py` to strip whitespace from authorization credentials per RFC 6750. Ideal basic agent plumbing test. |
| 2 | **`rich_4070`** | `Textualize/rich` | `multi_file` | `fc41075a` | Problem statement explicitly outlines coordinated import deferrals and type-checking optimizations spanning multiple components (`rich/logging.py` and `rich/console.py`). |
| 3 | **`fastapi_14479`** | `fastapi/fastapi` | `test_driven` | `2b212ddd` | Problem statement provides an executable reproduction script with FastAPI/Pydantic, exact "Stacktrace before" with uninformative `AssertionError`, and exact "Stacktrace after" specifying the required error message: `AssertionError: Query param 'data' must be of one of the supported types`. |
| 4 | **`requests_6629`** | `psf/requests` | `misleading_surface_symptom` | `7a13c041` | Reported user symptom is a multiprocessing pool crash upon JSON decode failure, which could superficially suggest worker or stream handling bugs; the true root cause lies in class inheritance MRO and pickle `__reduce__` in `requests.exceptions.JSONDecodeError`. |
| 5 | **`requests_7505`** | `psf/requests` | `graph_retrieval_candidate` | `6f205ff4` | Problem statement identifies that protocol `isinstance` checks (specifically `SupportsRead`) fail on proxied objects across multiple call sites in the repository, making caller-callee and reference graph traversal (`get_code_neighbors`, `get_code_subgraph`) directly useful for finding all affected usages. |

---

## 4. Repository Distribution

| Repository | Source Task Count | Smoke Set Count | Proportion |
|---|:---:|:---:|:---:|
| **`fastapi/fastapi`** | 67 (51.9%) | 2 | 40% |
| **`psf/requests`** | 13 (10.1%) | 2 | 40% |
| **`Textualize/rich`** | 48 (37.2%) | 1 | 20% |
| **`encode/httpx`** | 1 (0.8%) | 0 | 0% |
| **Total** | **129** | **5** | **100%** |

*Note on `encode/httpx`:* The single httpx task (`httpx_3672`) in the dataset contains a very brief multi-point refactor bullet list. The selected tasks in `fastapi`, `requests`, and `rich` provide much stronger, verifiable category alignment for the 5 target engineering patterns while covering 99.2% of the benchmark repository domain.

---

## 5. Machine-Readable Manifest Format

The smoke set is serialized to [benchmark/tasks/smoke.jsonl](file:///e:/Projects/Impulse/benchmark/tasks/smoke.jsonl) with the schema:

```json
{
  "instance_id": "<str>",
  "repo": "<str>",
  "base_commit": "<str>",
  "category": "<str>",
  "selection_rationale": "<str>"
}
```

Ground-truth solutions and test patches are intentionally excluded to maintain strict benchmark hygiene.
