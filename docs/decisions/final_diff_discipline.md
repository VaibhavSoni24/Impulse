# Architecture Decision Record: Final Diff Discipline & Repository Hygiene (Stage 27)

## Status
ACCEPTED (Stage 27 Implementation)

## Context
During iterative development of complex autonomous multi-agent systems, repositories accumulate development residue:
- Local scratch files (`scratch.py`, `tmp_*.py`, test patch dumps);
- Ephemeral execution traces and local logs (`*.log`, `*.trace`);
- Transient debug markers (`breakpoint()`, `pdb.set_trace()`, ad-hoc `print("DEBUG...")`);
- Machine-specific caches (`__pycache__`, `.pytest_cache`, `.venv/`, IDE metadata);
- Hardcoded local workstation paths (`C:\Users\...`, `/home/...`);
- Untracked or local environment configurations (`.env`).

Unprincipled or aggressive automated deletion ("`git clean -fd`") poses severe risks:
1. Accidental deletion of legitimate synthetic fixtures (e.g. `tests/fixtures/compaction_fixtures.py`, `tests/fixtures/budget_fixtures.py`);
2. Deletion of authoritative benchmark manifests, evaluation databases, or candidate definitions;
3. Silent loss of experiment provenance and execution reports;
4. Destruction of uncommitted but valid developer work.

To resolve these tensions deterministically, PLAN.md Stage 27 establishes **Final Diff Discipline**: a structured, non-destructive repository hygiene and pre-release verification system.

---

## Decision

### 1. Mandatory Git Review Sequence
Every stage completion and candidate release requires execution of the deterministic review sequence:
1. `git status --short`: Parse and categorize working tree file states (`MODIFIED`, `ADDED`, `DELETED`, `RENAMED`, `UNTRACKED`, `IGNORED`).
2. `git diff --stat`: Measure scope of changes.
3. `git diff --name-status`: Inspect precise file change taxonomy.
4. `git diff -- <relevant tracked files>`: Inspect granular modifications to tracked code.
5. Untracked file audit: Classify and inspect all unversioned files.
6. Suspicious ignored file inspection: Detect accidental ignored pollution.
7. Artifact classification & hygiene scan: Map files into canonical categories.
8. Security / Secret scan: Ensure zero credential leakage.
9. Test rerun evaluation: Enforce re-execution of test suites if tracked source code changed.
10. Final cleanliness report: Produce a deterministic, machine-readable `HygieneReport`.

### 2. Artifact Classification Policy (14 Canonical Classes)
The repository enforces 14 explicit artifact categories:

| Artifact Class | Description | Default Action |
|---|---|---|
| `REQUIRED_SOURCE` | Core agent, local subsystem, test suite, and CLI source code (`agent/`, `local/`, `tests/`, `scripts/`). | `KEEP` |
| `REQUIRED_CONFIG` | Authoritative repository configuration (`pyproject.toml`, `.gitignore`, `uv.lock`, `.env.example`). | `KEEP` |
| `REQUIRED_DOCUMENTATION` | Governance documents, ADRs, and guides (`AGENTS.md`, `IMPULSE.md`, `PLAN.md`, `README.md`, `docs/`). | `KEEP` |
| `REQUIRED_TEST_FIXTURE` | Permanent versioned test fixtures (`tests/fixtures/*`). | `KEEP` |
| `REQUIRED_EXPERIMENT_ARTIFACT` | Multi-agent candidate packages and evaluation databases (`experiments/candidates/*`). | `KEEP` |
| `REQUIRED_REPORT` | Authoritative stage execution reports (`experiments/prompts/*_report.md`). | `KEEP` |
| `REQUIRED_BENCHMARK_DATA` | Canonical benchmark datasets and task manifests (`benchmark/*`). | `KEEP` |
| `GENERATED_BUT_TRACKED` | Compiled candidate summaries, tracked synthetic splits, and tracked digests. | `KEEP` |
| `IGNORED_LOCAL_ARTIFACT` | Local developer caches, `.venv/`, matching `.gitignore`. | `KEEP` / `REVIEW` |
| `SCRATCH_ARTIFACT` | Ad-hoc development scripts, temporary patch dumps, editor backups (`scratch.py`, `tmp_*.py`, `.bak`, `.tmp`). | `REMOVE` (untracked, unreferenced) / `REVIEW` |
| `DEBUG_ARTIFACT` | Tracked logs, execution traces, or files containing temporary debug statements. | `REVIEW` |
| `MACHINE_SPECIFIC_ARTIFACT` | Bytecode directories (`__pycache__`), `.pytest_cache`, or hardcoded local workstation paths. | `REMOVE` (untracked cache) / `REVIEW` |
| `SECRET_OR_CREDENTIAL` | `.env`, API keys, private keys, access tokens. | `REVIEW` (blocking) |
| `UNKNOWN` | Unrecognized files outside standard conventions. | `REVIEW` (REPORT, NEVER REMOVE) |

### 3. Non-Destructive Cleanup & Safety Rules
Automatic deletion is strictly conservative:
- **No Global Destructive Commands:** Commands such as `git clean -fd` are strictly prohibited in automated agents and scripts.
- **Tracked Files are Never Automatically Deleted:** Tracked files require explicit manual git review and removal.
- **Protected Paths Invariant:** Any path under `agent/`, `benchmark/`, `docs/`, `.agents/`, `experiments/candidates/`, `experiments/prompts/`, or `tests/fixtures/` cannot be automatically removed.
- **Referential Safety Check:** Prior to recommending or executing removal, the `ReferenceChecker` inspects the repository. If any file (code, test, markdown link, YAML include, or manifest) references the candidate file, removal is rejected and downgraded to `REVIEW` or `KEEP`.
- **High Confidence Requirement:** Only untracked scratch artifacts with confidence >= 0.90, confirmed unreferenced, and outside protected paths may be cleaned.
- **Default for Unknowns:** `UNKNOWN` artifacts are reported in diagnostics, NEVER deleted.

### 4. Debug Marker Policy
Source-level inspection scans code for transient development residue:
- High-confidence debug markers: `breakpoint()`, `pdb.set_trace()`, `import pdb`, `pdb.post_mortem()`.
- Temporary print markers: `print("DEBUG...")`, `console.log("DEBUG...")`.
- Legitimate logging infrastructure (`logger.info`, `logger.debug`, `logging.getLogger`) and CLI output print statements in scripts (`scripts/validate_submission.py`) are preserved.

### 5. Local Configuration & Machine-Specific Artifact Policy
- **Configuration Templates:** `.env.example` is explicitly classified as `REQUIRED_CONFIG` (`KEEP`).
- **Actual Local Configs:** `.env`, `credentials.json`, `secrets.json` are classified as `SECRET_OR_CREDENTIAL` or `IGNORED_LOCAL_ARTIFACT` (`REVIEW`).
- **Machine Paths:** Scans for Windows absolute paths (`C:\Users\...`) and Unix user paths (`/home/...`). Informational documentation is reviewed with lower confidence; code paths require review and replacement with relative paths.

### 6. Secret & Security Hygiene Policy
- Inspects code and diffs for API keys, tokens (`ghp_`, `AKIA`, `sk-`), and private key headers.
- **Masking Mandate:** Secrets must NEVER be emitted into reports, logs, commit messages, or diff summaries. Findings are recorded as `[SECRET_DETECTED_IN_PATH]`.

### 7. Test Rerun Rule
If any cleanup or review action modifies a tracked Python file in `agent/`, `local/`, or `tests/`, `requires_test_rerun` is set to `True`, mandating re-execution of relevant focused and regression test suites.

---

## Consequences
- **Positive:** Unintended repository pollution is immediately visible; legitimate fixtures and reports are provably protected; secrets and machine-specific artifacts are prevented from reaching commits.
- **Positive:** Completely reproducible pre-release audits via `scripts/final_diff_review.py`.
- **Negative:** Requires running the review pipeline before declaring a stage complete.
