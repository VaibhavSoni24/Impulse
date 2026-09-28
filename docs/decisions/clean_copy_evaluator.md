# Architecture Decision Record: Clean-Copy Evaluator (Stage 28)

- **Status:** ACCEPTED & FROZEN
- **Date:** 2026-09-28
- **Parent Stage:** Stage 27 (Final Diff Discipline & Pre-Release Hygiene)
- **Authoritative Plan Reference:** PLAN.md Stage 28
- **Primary Objective:** Build an evaluation harness that verifies agent submissions strictly against clean, isolated repository snapshots rather than dirty agent workspaces.

---

## 1. Context and Problem Statement

In automated software engineering (SWE) benchmark competitions, the grading system evaluates a candidate patch by applying it to a completely fresh, unmutated checkout of the benchmark repository at a designated base commit. If an agent succeeds only because it created untracked local side-effects, left auxiliary scripts in the workspace, modified unsubmitted files, or relied on ambient environment state, the patch will fail when evaluated in the competition grading harness.

Prior to Stage 28:
- The initial local task runner evaluated tasks directly in the working tree or shared directories.
- Dirty agent workspaces could mask uncommitted or untracked changes.
- Untracked files intended for submission could be missed by naive `git diff` operations.
- Destructive operations (`git reset --hard`, `git clean -fdx`) posed catastrophic risks if executed on developer repositories.

Stage 28 builds the authoritative Clean-Copy Evaluator to eliminate these failure modes by enforcing the exact competition evaluation boundary locally.

---

## 2. Core Architectural Flow

The evaluator executes the following strict 7-phase lifecycle for every task:

```
[Clean Repository Snapshot #1 (Agent)]
               ↓
       [Load Candidate]
               ↓
          [Run Agent]
               ↓
        [Extract Patch]
               ↓
[Clean Repository Snapshot #2 (Validation)]
               ↓
    [Apply Patch to Clean Copy]
               ↓
        [Run Verification]
               ↓
    [Record Result & Dispose]
```

At no point does the evaluator treat "the agent workspace passes tests" as sufficient evidence of success. Only clean-copy verification determines task outcome.

---

## 3. Subsystem Architecture

### 3.1 Clean Repository Snapshot (`local/clean_copy/snapshot.py`)
- **`CleanRepositorySnapshot`**: An isolated workspace possessing:
  - Base commit SHA identity.
  - Run ID and Task ID binding.
  - Dedicated isolated filesystem path outside the main working tree (under tempdir/worktrees).
  - Clean initial Git status (verified via `git status --short`).
  - Standard Git exclude configuration (`core.excludesFile`) ensuring caches (`__pycache__`, `.pytest_cache`, `.coverage`) are hermetically ignored without mutating developer configs.
- **`SnapshotManager`**:
  - Verifies developer baseline cleanliness before launching evaluations (rejects dirty baselines unless explicit override is provided).
  - Primary mechanism: `git worktree add --detach <workspace_dir> <commit_sha>`.
  - Fallback mechanism: `git clone --shared --no-checkout` + `git checkout <commit_sha>`.
  - Safe disposal with Windows read-only file permission handling (`_remove_readonly`).

### 3.2 Candidate Loading (`local/clean_copy/candidate_loader.py`)
- **`CandidateLoader`**:
  - Deterministically resolves candidate packages (`M0` through `M5` or custom).
  - Executes structural validation using competition `SubmissionValidator`.
  - Computes cryptographic SHA-256 hashes of `agent.yaml`, root/specialist prompts, and complete candidate bundles.
  - Materializes candidate configuration into execution environments without mutating source candidate definitions.

### 3.3 Agent Execution Adapter (`local/clean_copy/adapter.py`)
- **`AgentExecutionAdapter`**:
  - Supports three mutually exclusive modes:
    1. `FIXTURE`: Deterministic fake agent for architectural and hermetic testing.
    2. `LIVE`: Execution against the competition model (`gemma-4-31b-it-qat-w4a16-ct`) when hardware and vLLM stack exist.
    3. `UNAVAILABLE`: Explicit status reported when host lacks required GPU hardware (4x NVIDIA L4, 96 GB VRAM) and local inference servers. Never fabricates results or silently downgrades live runs to fixtures.

### 3.4 Patch Extraction (`local/clean_copy/patch_extractor.py`)
- **`PatchExtractor`**:
  - Enforces the competition patch capture sequence:
    1. `git add -N .`: Stages untracked file intents while honoring `.git/info/exclude` / `core.excludesFile`.
    2. `git diff HEAD`: Captures complete unified diff including file creations (`/dev/null` additions), modifications, and deletions.
    3. `git diff --name-status HEAD`: Identifies modified, added, and deleted paths.
  - Enforces security boundaries:
    - Rejects path traversal (`../`) and absolute paths.
    - Rejects committed secrets (scanned via `scan_content_for_secrets`).
    - Rejects evaluator internal directories or temporary files.
  - Produces a deterministic `PatchBundle`.

### 3.5 Fresh Patch Application (`local/clean_copy/patch_applier.py`)
- **`FreshPatchApplier`**:
  - Creates a completely fresh validation snapshot at the identical baseline commit.
  - Applies patch using `git apply --whitespace=nowarn`.
  - Classifies failures as `PATCH_APPLY_CONFLICT` rather than task regression.
  - Verifies expected file creations and deletions.

### 3.6 Patch Equivalence (`local/clean_copy/equivalence.py`)
- **`PatchEquivalenceChecker`**:
  - Compares the agent workspace files with the fresh validation workspace files.
  - Performs semantic content SHA-256 comparisons across all changed paths rather than brittle whitespace diff comparisons.

### 3.7 Verification (`local/clean_copy/verifier.py`)
- **`CleanCopyVerifier`**:
  - Executes task verification commands exclusively inside the clean validation workspace.
  - Captures exit code, stdout, stderr, execution duration, and failure diagnostics.

### 3.8 Evaluation Storage & Ingestion (`local/evaluation/`)
- Integrates into existing IMPULSE SQLite database (`eval.db`).
- Added clean-copy fields to `runs` schema:
  - `baseline_commit`
  - `candidate_config_sha256`
  - `patch_sha256`
  - `patch_extraction_status`
  - `patch_apply_status`
  - `verification_status`
  - `failure_stage`
  - `workspace_isolated`
  - `clean_copy_verified`
- Idempotent schema migration preserves historical data from prior stages.

---

## 4. Failure Stage Taxonomy

To clearly separate evaluator infrastructure errors from agent solution errors, Stage 28 defines explicit failure stages:

| Failure Stage | Description | Example Failure Class |
|---|---|---|
| `PREPARE` | Failed baseline check or snapshot creation | `BASELINE_NOT_CLEAN`, `TASK_NOT_FOUND` |
| `CANDIDATE_LOAD` | Candidate bundle invalid or malformed | `CANDIDATE_INVALID` |
| `AGENT_EXECUTION` | Agent timed out, crashed, or runtime missing | `RUNTIME_UNAVAILABLE`, `AGENT_TIMEOUT` |
| `PATCH_EXTRACTION` | Patch command failed or secret detected | `PATCH_EXTRACTION_FAILURE` |
| `PATCH_APPLICATION` | Patch did not apply cleanly to fresh repo | `PATCH_APPLY_CONFLICT` |
| `VERIFICATION` | Clean copy test command failed | `VERIFICATION_TEST_FAILURE` |
| `CLEANUP` | Workspace disposal failed | `CLEANUP_FAILURE` |

---

## 5. Security & Isolation Guarantees

1. **Zero Dev-Repo Mutation**: Destructive git commands (`git reset --hard`, `git clean -fdx`) are strictly forbidden against developer repositories. They operate exclusively inside disposable workspaces.
2. **Credential Isolation**: `.env`, credentials, and private keys are excluded from snapshots and validated during patch extraction.
3. **Multi-Task Isolation**: Every task run receives a unique, disposable directory. Tasks never share mutable working directories.
4. **Candidate Immutability**: Source candidate directories (`experiments/candidates/M0-M5`) remain read-only; materialization happens into isolated scratch directories.

---

## 6. Known Limitations

- **Local Live Model Execution**: The local Windows development machine lacks 4x NVIDIA L4 GPUs and vLLM server. Live execution correctly flags `UNAVAILABLE`.
- **Operating System Portability**: Git worktree removal on Windows requires explicit read-only permission clearing (`_remove_readonly`) which is fully handled.
- **Stage Boundary**: Stage 28 covers evaluator infrastructure only. Dataset split construction (Stage 29), dashboards (Stage 30), and LoRA are strictly out of scope.
