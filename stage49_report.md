# IMPULSE — Stage 49 Completion Report: Submission Configuration Audit

**Stage Name:** Stage 49 — Submission Configuration Audit  
**Parent Commit:** `70404ba504d6e9935ee5222ef45b4c1aa5610ec3` (`feat: add deterministic submission packager`)  
**Commit Message:** `fix: enforce single base model policy and audit configs`  
**Execution Environment:** Windows 10 (Python 3.10.11), Local CPU (`Intel(R) Iris(R) Xe Graphics`), Zero GPU  
**Date:** 2026-10-23  

---

## 1. Executive Summary

In Stage 49 of the IMPULSE project, we performed a comprehensive, authoritative audit of all submission configuration files across the repository, established strict single-base-model enforcement conforming to the official competition environment (`swegemma`), and formalized configuration policy compliance across all candidate packages (M0 through M5) and sample submissions.

Key achievements:
1. **Authoritative Runtime Model String Audit:** Verified against competition environment sources (`swegemma/config.py`, official runner specs) that exactly four quantized Gemma 4 model families are supported by the Kaggle container runtime:
   - `gemma-4-31b-it-qat-w4a16-ct` (Primary canonical model for IMPULSE)
   - `gemma-4-12b-it-qat-w4a16-ct`
   - `gemma-4-e4b-it-qat-w4a16-ct`
   - `gemma-4-e2b-it-qat-w4a16-ct`
2. **Single-Base-Model Policy Enforcement:** Enforced that within any single candidate package (submission), the root agent and all specialist sub-agents (e.g., Scout, Debugger, Reviewer) must declare the **identical base model** (`gemma-4-31b-it-qat-w4a16-ct`). This reflects the physical container constraints of Kaggle evaluation environments (dual T4 / single L4 GPU limit of 24 GB VRAM), where hosting multiple model weights in memory concurrently causes out-of-memory container termination.
3. **Model Alias Normalization Subsystem:** Implemented transparent model alias resolution supporting common prefix variants (`google/`, `hosted_vllm/`, `vllm/`, `huggingface/`, `hf/`, `vertex_ai/`) mapping deterministically to canonical runtime model strings.
4. **Candidate Package Audit (M0–M5):** Audited every configuration file across candidates M0, M1, M2, M3, M4, and M5, verifying 100% adherence to allowed models, tool boundaries, generation parameters, context limits, and absence of forbidden fields or credentials.
5. **Adversarial and Regression Verification:** Created 22 comprehensive tests in `tests/test_configuration_audit_stage49.py` covering model validation, alias resolution, multi-agent uniform model enforcement, YAML schema compliance, and diagnostic integrity.
6. **Zero Regressions:** Validated candidate packages M0–M5 (all PASS), verified Stage 24 frozen artifacts (14/14 MATCH), verified Stage 45 regression suite (20 PASS, 2 BLOCKED), verified Stage 46 stress test suite (20 PASS), and verified packaging suite (99 focused packaging tests passing).

---

## 2. Configuration Audit Findings

### 2.1 Supported Runtime Model Strings
From `swegemma/config.py` and competition container specifications:
- `gemma-4-31b-it-qat-w4a16-ct` (31B QAT W4A16 compressed-tensors) — **Selected Primary for IMPULSE**
- `gemma-4-12b-it-qat-w4a16-ct` (12B QAT W4A16 compressed-tensors)
- `gemma-4-e4b-it-qat-w4a16-ct` (4B QAT W4A16 compressed-tensors)
- `gemma-4-e2b-it-qat-w4a16-ct` (2B QAT W4A16 compressed-tensors)

Any other model identifiers (including unquantized bfloat16 models, older Gemma 1/2/3 variants, or third-party models) are rejected with diagnostic code `INVALID_BASE_MODEL`.

### 2.2 Model Alias Resolution Matrix
To prevent false rejections of valid submissions using standard ADK/vLLM model provider prefixes, the validator normalizes the following aliases:

| Input Alias / Specification | Canonical Resolved Model | Status |
|-----------------------------|---------------------------|--------|
| `gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` | Canonical (Direct Match) |
| `hosted_vllm/gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` | Normalized |
| `google/gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` | Normalized |
| `vllm/gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` | Normalized |
| `hf/gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` | Normalized |
| `vertex_ai/gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` | Normalized |
| `hosted_vllm/gemma-4-12b-it-qat-w4a16-ct` | `gemma-4-12b-it-qat-w4a16-ct` | Normalized |
| `google/gemma-4-e4b-it-qat-w4a16-ct` | `gemma-4-e4b-it-qat-w4a16-ct` | Normalized |
| `vllm/gemma-4-e2b-it-qat-w4a16-ct` | `gemma-4-e2b-it-qat-w4a16-ct` | Normalized |
| `llama-3-70b-instruct` | *(None)* | Rejected (`INVALID_BASE_MODEL`) |
| `gemma-2-27b-it` | *(None)* | Rejected (`INVALID_BASE_MODEL`) |

### 2.3 Single-Base-Model Policy Rationale
The competition execution environment provisions a single model server process (vLLM instance) serving local weights.
- **VRAM Boundary:** Gemma 4 31B W4A16 requires ~21–23 GB VRAM. Attempting to load an additional model (even 12B or 4B) causes CUDA OOM (`torch.cuda.OutOfMemoryError`) and runner crash.
- **Process Architecture:** The evaluation harness runs in isolated Docker containers with zero network access; external model API endpoints cannot be called.
- **Rule Requirement:** The configuration audit enforces that `model` declared in `agent.yaml` must match across all sub-agents defined in `sub_agents`. Mixing models within an archive raises `MULTI_MODEL_VIOLATION`.

---

## 3. Audited Candidate Packages

Every candidate package in `experiments/candidates/` and baseline sample submissions were audited against Stage 49 configuration policies:

| Candidate ID | Root Agent Model | Sub-Agents Configured | Sub-Agent Models | Tool Count | Forbidden Keys | Secrets Found | Validation Status |
|---|---|---|---|---|---|---|---|
| `M0` | `gemma-4-31b-it-qat-w4a16-ct` | None (Root Only) | N/A | 9 | None | 0 | **PASS** |
| `M1` | `gemma-4-31b-it-qat-w4a16-ct` | Scout | `gemma-4-31b-it-qat-w4a16-ct` | 9 | None | 0 | **PASS** |
| `M2` | `gemma-4-31b-it-qat-w4a16-ct` | Scout, Debugger | `gemma-4-31b-it-qat-w4a16-ct` | 9 | None | 0 | **PASS** |
| `M3` | `gemma-4-31b-it-qat-w4a16-ct` | Scout, Debugger, Reviewer | `gemma-4-31b-it-qat-w4a16-ct` | 9 | None | 0 | **PASS** |
| `M4` | `gemma-4-31b-it-qat-w4a16-ct` | Scout, Debugger, Reviewer | `gemma-4-31b-it-qat-w4a16-ct` | 9 | None | 0 | **PASS** |
| `M5` | `gemma-4-31b-it-qat-w4a16-ct` | Scout, Debugger, Reviewer | `gemma-4-31b-it-qat-w4a16-ct` | 9 | None | 0 | **PASS** |
| `sample_submission` | `gemma-4-31b-it-qat-w4a16-ct` | None | N/A | 9 | None | 0 | **PASS** |

### Findings & Corrective Actions
- **All M0–M5 candidates:** Correctly declared `gemma-4-31b-it-qat-w4a16-ct` uniformly across all root agents and sub-agents.
- **Tool Boundary Integrity:** Root agents preserve exactly the 9 predefined competition tools; sub-agents preserve authorized read-only subsets (Scout: 5 tools; Debugger: 5 tools; Reviewer: 5 tools).
- **Zero Forbidden Keys:** No `api_key`, `token`, `password`, `secret`, or `credentials` fields were detected in any audited configuration file.
- **Zero Deviations Requiring Fixes in M0–M5:** All candidate configurations strictly complied with the authoritative specification.

---

## 4. Test & Verification Results

### 4.1 Focused Test Suite: `tests/test_configuration_audit_stage49.py`
The test suite exercises 22 targeted scenarios:
- **Canonical Model Resolution:** 4 tests verifying `31b`, `12b`, `e4b`, and `e2b` acceptance.
- **Unsupported Model Rejection:** 2 tests verifying arbitrary and older model rejection.
- **Provider Prefix Alias Normalization:** 5 tests verifying `hosted_vllm/`, `google/`, `vllm/`, `hf/`, `vertex_ai/`.
- **Multi-Agent Homogeneity Enforcement:** 3 tests verifying mixed models are rejected with `MULTI_MODEL_VIOLATION`, while identical models pass.
- **YAML Schema and Tool Discipline:** 3 tests verifying prohibited fields, context limits, and generation parameters.
- **Diagnostic API & JSON Output:** 3 tests verifying structured JSON output and check identifiers compatibility.
- **Real Candidate & Sample Verification:** 2 tests verifying M0–M5 and sample submission directory pass validation.

**Result:** `22 passed in 7.23s` (100% pass rate).

### 4.2 Packaging & Validation Battery
Combined execution of all packaging stages:
- Stage 47 (Package Validator): 51 tests passed.
- Stage 48 (Deterministic Packager): 26 tests passed.
- Stage 49 (Configuration Audit): 22 tests passed.
- **Total Packaging Tests:** **99 passed, 0 failed**.

### 4.3 Regression & Integrity Verification
1. **Stage 45 Failure Regression Suite:** `tests/test_failure_regression_stage45.py` -> **20 PASS, 0 FAIL, 2 BLOCKED** in 16.10s.
2. **Stage 46 Stress Test Suite:** `tests/test_stress_stage46.py` -> **20 PASS, 0 FAIL** in 10.34s.
3. **Stage 24 Frozen Artifacts:** `verify_frozen_artifacts()` -> **14/14 MATCH** (100% hash parity).
4. **Full Test Discovery Suite:** Ran 1,385+ tests across all 44 test modules; zero regressions across all core agent subsystems.

---

## 5. Artifact Ledger

| Path | Category | Purpose / Description |
|---|---|---|
| `docs/experiments/configuration_audit.md` | Documentation | Authoritative model policy, alias specification, and candidate audit findings |
| `local/packaging/constants.py` | Implementation | Added `SUPPORTED_BASE_MODELS`, `MODEL_PREFIX_ALIASES`, `resolve_canonical_model` |
| `local/packaging/config_validator.py` | Implementation | Updated model validation, alias resolution, and multi-agent model homogeneity |
| `tests/test_configuration_audit_stage49.py` | Verification | 22 comprehensive unit and adversarial tests for Stage 49 |
| `experiments/packaging/stage49_report.md` | Empirical Report | Detailed Stage 49 completion report and audit ledger |
| `stage49_report.md` | Empirical Report | Root mirror of Stage 49 completion report |

---

## 6. Conclusion & Gate Readiness

Stage 49 has successfully established strict submission configuration auditing and verified 100% compliance across candidate packages M0–M5. The repository is fully prepared for Stage 50 (Dry Run Validation & Readiness Assessment).
