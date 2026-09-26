# Patch Extraction & Capture Semantics — IMPULSE

**Document ID:** DEC-PATCH-CAPTURE  
**Status:** Authoritative / Verified via Documentation & Local Git Reproduction  
**Date:** 2026-09-26  
**Related Specifications:** [HARNESS_README.md](file:///E:/Projects/Impulse/data/competition/HARNESS_README.md), [tool_contracts.md](file:///E:/Projects/Impulse/docs/decisions/tool_contracts.md), [evaluator_flow.md](file:///E:/Projects/Impulse/docs/decisions/evaluator_flow.md), [PLAN.md](file:///E:/Projects/Impulse/PLAN.md)

---

## 1. Executive Summary & Objective

In the Google Gemma 4 Developer Agent Competition, an agent's solution is submitted and evaluated as a unified Git patch (`agent_patch`). The official scoring harness evaluates this patch in an isolated secondary container (Container B) against secret and validation test suites.

This document records the exact authoritative operational mechanics of patch capture as documented by the competition harness source and specifications (`HARNESS_README.md`), defines the local verification boundary, and details the local Git-level reproduction tests used to ensure that IMPULSE generates compliant, uncontaminated patches.

---

## 2. Authoritative Competition Contract (`submit_patch`)

The competition documentation provides unambiguous specifications for how `submit_patch()` operates, how fallback extraction functions, and how repository state is translated into the candidate patch.

### 2.1. Tool Signature & Budget Properties
*Source Reference: `data/competition/HARNESS_README.md`, Section 6.2 (Lines 394–401), Section 9.3 (Lines 652–654); `docs/decisions/tool_contracts.md`, Section 3.2.*

- **Signature:** `submit_patch() -> str`
- **Parameters:** None.
- **Budget Gated:** Yes (enforced by `@budget_gated(count_tool_call=False)`).
- **Tool Budget Debit:** **No** (`count_tool_call=False`). Calling `submit_patch()` does **not** decrement the remaining `tool_calls` allowance.
- **Budget Exhaustion Behavior:** It can still be called when `tool_calls_remaining == 0` (or `tool_calls_used == max_tool_calls`), provided that session wall-clock time has not expired.
- **Session Lifecycle Effect:** Sets `context.patch_submitted = True`. The agent loop is **not terminated mid-turn**; instead, the harness allows the agent to finish its response for the current turn, and once the turn completes with `patch_submitted == True`, the harness immediately breaks the loop and proceeds to Phase 2 verification (`verify_task`).
- **Return Payload Schema:**
  ```json
  {"status": "ok", "patch_size": 1420, "files_changed": 2}
  ```

### 2.2. Baseline Commit & Working Tree Preparation
*Source Reference: `data/competition/HARNESS_README.md`, Section 4.1 (Lines 255–282).*

Before the agent starts running in Container A, the competition harness prepares `/workspace`:
1. **Snapshot Extraction:** Extracts the repository snapshot at `base_commit`. Commits after `base_commit` do not exist in `.git`.
2. **Git Exclude Rules:** Appends standard build/test patterns to `/workspace/.git/info/exclude`:
   ```text
   __pycache__/
   *.pyc
   .pytest_cache/
   *.egg-info/
   build/
   dist/
   .coverage
   ```
3. **Hermetic Test Config:** Writes standardized `/workspace/pytest.ini` and hooks `/workspace/conftest.py`.
4. **Baseline Commit Creation:** Executes:
   ```bash
   cd /workspace && git add -A && git commit -m "baseline" --allow-empty -q
   ```
   Consequently, the baseline `HEAD` in `/workspace` includes the task repository code plus the initial harness configuration files.

### 2.3. Patch Extraction Command Sequence
*Source Reference: `data/competition/HARNESS_README.md`, Section 8.1 (Lines 554–564).*

When `submit_patch()` is invoked (or during automatic fallback), the harness executes the exact following shell commands inside `/workspace` in Container A:
```bash
cd /workspace && git add -N .
cd /workspace && git diff HEAD
```

#### Why `git add -N .` (Intent-to-Add) Matters:
- Standard `git diff HEAD` only tracks modifications to files already indexed in Git. Unstaged untracked files are completely omitted from `git diff HEAD`.
- `git add -N .` (`--intent-to-add`) adds an entry for each untracked path into the Git index with empty contents, without staging the file contents.
- As a direct result, subsequent `git diff HEAD` captures:
  1. Modifications to existing tracked files;
  2. Deleted tracked files;
  3. **Newly created files** (represented as unified diff additions from `/dev/null`).
- Files matching patterns in `/workspace/.git/info/exclude` (e.g. `__pycache__/`, `*.pyc`) are ignored by `git add -N .` and will **not** be indexed or captured.

### 2.4. Automatic Unsubmitted Patch Recovery (Fallback)
*Source Reference: `data/competition/HARNESS_README.md`, Section 8.1 (Lines 561–564).*

If an agent finishes, exhausts its turns or tool budget, hits `max_nudges` (3 consecutive text responses without tool calls), or times out without ever calling `submit_patch()`:
1. The harness automatically executes:
   ```bash
   cd /workspace && git add -N . && git diff HEAD
   ```
2. If `agent_patch != ""` (the working tree contains uncommitted changes), the evaluator **still proceeds to Phase 2 verification** in Container B, even if an `agent_error` was flagged.

### 2.5. Accidental File Contamination Risk & Hygiene Protocol
*Source Reference: `data/competition/HARNESS_README.md`, Section 9.3 (Lines 648–650).*

Because `git add -N .` indexes **all** non-excluded untracked files in `/workspace`:
- Any scratch file, debug script, or log created directly in `/workspace` (e.g., `/workspace/repro.py`, `/workspace/debug.log`) **will be indexed and captured into the final patch**.
- A patch contaminated with scratch scripts or debug artifacts can cause:
  - Patch application failures in Container B (`git apply` or `patch` rejecting non-essential changes);
  - Style/lint check failures;
  - Evaluation rejections.
- **Mandatory Hygiene Rule:**
  - Any reproduction script or debug probe must be written to **`/tmp/`** (e.g., `/tmp/repro.py`), which resides outside `/workspace`.
  - Alternatively, if any temporary files are created under `/workspace`, they must be explicitly removed before calling `submit_patch()`.

---

## 3. Boundary & Limitation Analysis

The competition infrastructure spans proprietary remote evaluation components and local development components. We explicitly distinguish what is verified and what remains unverified locally:

| Dimension | Classification | Status & Evidence |
|---|:---:|---|
| `submit_patch()` tool interface & schema | **OFFICIAL** | Formally documented in `HARNESS_README.md` (Sec 6.2, 8.1, 9.3) and `sample_submission/agent.yaml`. |
| Git commands (`git add -N . && git diff HEAD`) | **OFFICIAL** | Stated verbatim in `HARNESS_README.md` Section 8.1. |
| Automatic unsubmitted patch fallback | **OFFICIAL** | Explicitly documented in `HARNESS_README.md` Section 8.1 (referencing `agent_runner.py` lines 706–740). |
| Git `.git/info/exclude` default patterns | **OFFICIAL** | Documented in `HARNESS_README.md` Section 4.1 (`setup_git_exclude`). |
| Proprietary `SwegemmaContext` execution | **UNAVAILABLE LOCALLY** | The remote evaluation harness (`swegemma` package and Docker Container A/B orchestration) is proprietary to the competition platform and is not locally executable on Windows. |
| Git-level diff capture semantics | **LOCAL REPRODUCTION** | Replicated and verified using isolated temporary Git repositories in `tests/packaging/test_patch_capture.py`. |
| Untracked file capture behavior | **LOCAL REPRODUCTION** | Verified locally: `git diff HEAD` alone omits untracked files; `git add -N .` followed by `git diff HEAD` captures them completely. |
| Scratch file contamination behavior | **LOCAL REPRODUCTION** | Verified locally: untracked files in root are captured, while files matched by `.git/info/exclude` or located in external directories (like `/tmp`) are omitted. |

---

## 4. Local Reproduction Design (`test_patch_capture.py`)

To verify the documented patch-capture semantics without pretending to run the proprietary competition tool, we implement pure Git-level reproduction tests in `tests/packaging/test_patch_capture.py`.

### 4.1. Design Principles & Isolation
1. **Zero Fake Harness:** We do NOT implement a dummy `submit_patch` tool that mimics remote server behavior. Instead, we implement clean, explicitly-named reproduction helper functions (`capture_patch_reproduction()`, `stage_untracked_intents()`).
2. **Total Test Isolation:**
   - Every test runs inside a throwaway temporary directory created via `tempfile.TemporaryDirectory`.
   - Each temporary directory initializes an independent Git repository (`git init`).
   - Local Git configuration sets throwaway author identity (`user.name "Test Runner"`, `user.email "test@eval.local"`).
   - Under no circumstances does the test read, modify, or interact with the IMPULSE repository `.git` directory.
   - All temporary directories are purged automatically upon test completion.
3. **Robust Semantic Assertions:**
   - Tests assert on diff structure (`diff --git a/... b/...`, `new file mode`, `--- a/...`, `+++ b/...`), added/removed content, and file paths.
   - Tests do not rely on machine-dependent timestamps or Git commit hashes.

### 4.2. Controlled Verification Scenarios
The reproduction test suite validates four distinct scenarios:

- **Scenario A — Tracked File Change:**
  Modifies an existing tracked file. Captures patch via `capture_patch_reproduction()`. Asserts the diff contains the modification with `-` and `+` line markers.
- **Scenario B — Untracked File Creation & Intent Staging:**
  Creates a new file. Verifies that `git diff HEAD` produces an empty patch. Executes `git add -N .` (`stage_untracked_intents()`) and re-runs `git diff HEAD`. Asserts the new file is captured with `new file mode` and addition markers.
- **Scenario C — Accidental Scratch/Debug File Contamination:**
  Creates an unintended scratch file (`repro.py`) alongside code changes. Captures patch. Confirms the scratch file is captured into the patch, proving the hazard. Then demonstrates that adding `repro.py` to `.git/info/exclude` or writing the scratch file outside the repository prevents contamination.
- **Scenario D — Multiple Mixed Changes:**
  Applies tracked modifications, creates intended new modules, creates excluded build artifacts (`__pycache__/`, `.pytest_cache/`), and verifies that the captured patch contains exactly the intended code modifications and new files while excluding build artifacts.

---

## 5. Remaining Uncertainties & Official Verification Gates

The following runtime aspects cannot be validated locally and will be verified when submitting to or testing within the official competition environment:
1. **Container Execution Latency:** Time taken by the container engine to run `git add -N . && git diff HEAD` on very large repositories (e.g. Django, SymPy).
2. **Proprietary Patch Size Warning Limits:** Exact thresholds at which the official `submit_patch()` tool emits warnings or truncates return summaries (the return payload schema records `patch_size` and `files_changed`, but remote max payload size limits may exist).
3. **4-Pass `git apply` Edge Cases:** Behavior of the harness `apply_patch_in_container` when applying patches with mixed line endings (CRLF vs LF) or symlinked paths. IMPULSE will enforce strict LF line endings across all agent edits to guarantee clean patch application across all 4 passes.
