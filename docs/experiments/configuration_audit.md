# IMPULSE — Submission Configuration Audit & Model Policy Reference (Stage 49)

This document records the configuration audit findings, authoritative model policy, multi-agent structural requirements, and cross-platform archive determinism analysis for the Google Gemma 4 Developer Agent Competition on Kaggle.

---

## 1. Executive Summary & Audit Objectives

Stage 49 conducts an exhaustive audit of agent submission configurations, harness constraints, and packaging invariants. The key objectives accomplished are:
1. **Model Policy Alignment:** Codify the official list of four Gemma 4 quantized models confirmed by Kaggle staff.
2. **Single-Base-Model Enforcement:** Verify that root agents and all specialist sub-agents within any submission package use the identical base model variant.
3. **Sub-Agent & Tool Syntax Validation:** Support both string paths and mapping specifications (`config_path`) while strictly failing malformed or empty declarations.
4. **Determinism Boundary Analysis:** Document the boundary between intra-host bit-for-bit archive determinism and cross-platform artifact reproducibility.
5. **Candidate Verification:** Audit all active IMPULSE candidates (M0–M5) against the unified model and configuration policy.

---

## 2. Authoritative Gemma 4 Competition Model Policy

### 2.1 Approved Model Variants

Kaggle staff and the competition host announced on the official discussion forum that the evaluation environment runs a local vLLM / llama.cpp inference backend serving quantized Gemma 4 checkpoints. Submissions must declare exactly one of the following four approved models:

| Model Identifier | Parameter Count | Quantization / Format | Intended Role | Local Validation Status |
| :--- | :--- | :--- | :--- | :--- |
| `gemma-4-31b-it-qat-w4a16-ct` | 31 Billion | QAT W4A16 Compressed Tensors | **Primary Flagship** (High Reasoning) | **APPROVED & DEFAULT** |
| `gemma-4-12b-it-qat-w4a16-ct` | 12 Billion | QAT W4A16 Compressed Tensors | Medium Specialist / High Throughput | **APPROVED** |
| `gemma-4-e4b-it-qat-w4a16-ct` | Effective 4B | QAT W4A16 Compressed Tensors | Compact Specialist / Low Latency | **APPROVED** |
| `gemma-4-e2b-it-qat-w4a16-ct` | Effective 2B | QAT W4A16 Compressed Tensors | Ultra-lightweight Utility / Routing | **APPROVED** |

### 2.2 Prohibited & Disallowed Models

Any submission declaring a model outside the four approved variants is rejected during pre-submission validation with `MODEL_PERMITTED_ALIAS: FAIL`. Specifically prohibited:
- **Unquantized Baselines:** `gemma-4-31b-it`, `gemma-4-12b-it`, `gemma-4-7b-it` (exceed runner VRAM limits).
- **Non-Standard Quantizations:** `gemma-4-31b-it-w4a16`, `gemma-4-31b-it-qat` (malformed or incomplete tags).
- **External & Closed Models:** `gpt-4`, `gpt-4o`, `claude-3-5-sonnet`, `mistral-7b` (no internet connectivity; proprietary APIs forbidden).
- **Fictitious / Custom Names:** `gemma-4-99b`, `custom-agent-v1`.

### 2.3 Provider Prefix Normalization

The validator and packager automatically normalize provider prefixes specified in `agent.yaml`. For example:
- `google/gemma-4-31b-it-qat-w4a16-ct` $\rightarrow$ `gemma-4-31b-it-qat-w4a16-ct`
- `hosted_vllm/gemma-4-12b-it-qat-w4a16-ct` $\rightarrow$ `gemma-4-12b-it-qat-w4a16-ct`
- `openai/gemma-4-e4b-it-qat-w4a16-ct` $\rightarrow$ `gemma-4-e4b-it-qat-w4a16-ct`

---

## 3. Multi-Agent & Single-Base-Model Invariant

### 3.1 The Single-Base-Model Rule

The competition evaluation runner provisions a single local model serving container per evaluation instance. Consequently:
- **Rule:** Every agent file (`agent.yaml`, `sub_agents/*.yaml`) within a submission package must declare the **exact same base model variant**.
- **Enforcement:** If a package declares `gemma-4-31b-it-qat-w4a16-ct` at the root and `gemma-4-12b-it-qat-w4a16-ct` in a sub-agent, the validator fails immediately with `MODEL_SINGLE_BASE: FAIL`.
- **PEFT LoRA Exception:** Adapters can differ between specialists, provided they attach to the identical underlying base model architecture and rank bounds ($\le 128$).

### 3.2 Sub-Agent & Agent-Tool Configuration Schema

The ADK framework and Kaggle competition starter kit accept two equivalent syntaxes for referencing child sub-agents:

#### Syntax A: Direct String Path
```yaml
sub_agents:
  - sub_agents/scout.yaml
  - sub_agents/debugger.yaml
```

#### Syntax B: Mapping Specification
```yaml
sub_agents:
  - config_path: sub_agents/scout.yaml
  - config_path: sub_agents/debugger.yaml
```

The IMPULSE validator supports both notations and strictly rejects:
1. Non-list declarations (`sub_agents: "path.yaml"`).
2. Unrecognized item types (integers, booleans, nested lists).
3. Mapping specifications lacking `config_path` or containing empty strings.
4. Relative paths pointing outside the submission package boundary.

The same dual-syntax rules apply to `agent_tool` declarations inside the `tools` list:
```yaml
tools:
  - read_file
  - edit_file
  - agent_tool: sub_agents/scout.yaml
  # or
  - agent_tool:
      config_path: sub_agents/scout.yaml
```

---

## 4. Cross-Platform Archive Determinism Findings

### 4.1 Intra-Host Bit-for-Bit Determinism

When running on a fixed environment (same operating system, Python build, and zlib implementation), the IMPULSE Deterministic Submission Packager guarantees **100% byte-for-byte reproducibility**:
- **Normalized Timestamps:** All ZIP headers set to `(2026, 1, 1, 0, 0, 0)`.
- **Lexicographical Ordering:** Member entries sorted alphabetically by POSIX path.
- **Normalized Permissions:** Fixed external attributes `0o100644 << 16` for regular files.
- **Fixed Compression:** DEFLATE at compression level 6 with standard flags.

### 4.2 Cross-Platform Audit Boundary

Our audit identified the following factors that can cause ZIP archive SHA-256 hashes to diverge across different operating systems (e.g. Windows vs Linux):

1. **Source File Line Endings (`CRLF` vs `LF`):**
   - On Windows, text files checked out without `.gitattributes` or with `core.autocrlf = true` may contain `\r\n` line endings.
   - On Linux containers, files contain `\n` line endings.
   - Because the packager streams raw bytes into the ZIP archive to guarantee exact payload fidelity without mutation, different line endings result in different uncompressed payloads and different archive hashes.
   - **Mitigation:** Repository-level `.gitattributes` forces `* text=auto eol=lf` across all tracked files.

2. **Python `zlib` Implementation Differences:**
   - Python's standard `zipfile` module delegates DEFLATE compression to the host system's `zlib` C library.
   - Minor implementation differences between Windows DLLs (MSVC build) and Linux shared objects (`libz.so`) can yield slightly different compressed Huffman bitstreams, even though the uncompressed payload and CRC-32 checksums are identical.
   - **Recommendation:** Official candidate release builds should be packaged inside the designated competition Docker container or runner image when absolute cross-platform byte equality is required.

---

## 5. Candidate Audit Matrix (M0–M5)

All active candidates in `experiments/candidates/` were audited against the updated Stage 49 configuration and model policy:

| Candidate ID | Agent Name | Architecture | Base Model | Skills | Adapters | Stage 49 Validation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **M0** | `impulse_m0_baseline` | Single Agent | `gemma-4-31b-it-qat-w4a16-ct` | 0 | 0 | **PASS (0 errors, 0 warnings)** |
| **M1** | `impulse_m1_root_plus_scout` | Root + Scout | `gemma-4-31b-it-qat-w4a16-ct` | 2 | 0 | **PASS (0 errors, 0 warnings)** |
| **M2** | `impulse_m2_root_scout_verifier` | Root + Scout + Verifier | `gemma-4-31b-it-qat-w4a16-ct` | 2 | 0 | **PASS (0 errors, 0 warnings)** |
| **M3** | `impulse_m3_dynamic_hierarchy` | Dynamic Team Hierarchy | `gemma-4-31b-it-qat-w4a16-ct` | 3 | 0 | **PASS (0 errors, 0 warnings)** |
| **M4** | `impulse_m4_tool_augmented` | Tool Specialist Network | `gemma-4-31b-it-qat-w4a16-ct` | 3 | 0 | **PASS (0 errors, 0 warnings)** |
| **M5** | `impulse_m5_resilient_ensemble` | Resilient Ensemble Pipeline | `gemma-4-31b-it-qat-w4a16-ct` | 4 | 0 | **PASS (0 errors, 0 warnings)** |

Every candidate adheres strictly to the single-base-model constraint and utilizes approved competition aliases.

---

## 6. Recommendations for Candidate Packaging

1. **Retain 31B Primary Base Model:** All current candidates M0–M5 effectively leverage `gemma-4-31b-it-qat-w4a16-ct`. We recommend retaining this model as the primary candidate base for benchmark submissions.
2. **Specialist Variant Exploration:** If latency or memory pressure arises during official container evaluation, `gemma-4-12b-it-qat-w4a16-ct` serves as the primary fallback candidate, applied uniformly across the entire agent hierarchy.
3. **Automated Pre-Flight Gate:** Always execute `python scripts/validate_submission.py <path> --strict --json` prior to any competition archive release.
