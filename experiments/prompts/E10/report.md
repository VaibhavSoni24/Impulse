# Candidate E10 Experiment Report: No-Progress Detection

**Candidate ID:** E10  
**Parent Candidate:** E9  
**Parent Git Commit:** `d8ed92d6c2ff347061aecfdb8068708dc4000be8`  
**Date:** 2026-09-26  
**Status:** Validated (Structural validation only; execution unasserted)

---

## 1. Motivation and Purpose (Stage 19)

In autonomous repository repair, agents frequently become trapped in unproductive, repetitive reasoning loops:
- Retrying identical or whitespace-only code edits across consecutive turns after test failures.
- Pursuing an identical failing root-cause hypothesis without obtaining new supporting evidence.
- Repeatedly executing the same test command against an unchanged working tree and expecting different results.
- Modifying unrelated documentation or scratch files while the target defect remains unaddressed.

Stage 19 implements a deterministic **No-Progress Detector** (`NoProgressDetectorV1`) to evaluate whether the agent has ceased making meaningful progress across verification cycles.

---

## 2. E9 → E10 Architecture Delta

```text
Candidate E9 (Stage 18):
  Model: gemma-4-31b-it-qat-w4a16-ct
  Tools: 9 competition tools
  Skills: [skills/test_strategy, skills/repo_triage]
  Policy: Repository triage + hybrid localization + testing strategy + 8-class failure taxonomy

Candidate E10 (Stage 19):
  Model: gemma-4-31b-it-qat-w4a16-ct (Preserved identical)
  Tools: 9 competition tools (Preserved identical; zero tools added or removed)
  Skills: [skills/test_strategy, skills/repo_triage] (Preserved identical)
  Delta: Added No-Progress Detection V1 (NoProgressDetectorV1, normalized fingerprinting),
         prompt instruction requiring explicit progress evaluation across cycles,
         and structured recording into TaskState.no_progress_count.
```

---

## 3. Progress vs. No-Progress State Model

The detector classifies transitions into three states:
- `PROGRESS`: Constructive change detected (verification passed, failure class changed, test signature changed, hypothesis revised, relevant source files modified, or new diagnostic evidence recorded).
- `NO_PROGRESS`: Unproductive repetition detected across $\ge$ threshold consecutive cycles.
- `INSUFFICIENT_EVIDENCE`: Diagnostic signals are missing or incomplete to evaluate causality.

### Supported No-Progress Reasons
1. `REPEATED_FAILURE`: Identical failure signature reproduced without improvement.
2. `REPEATED_HYPOTHESIS`: Identical hypothesis pursued across cycles without revision.
3. `REPEATED_EDIT`: Materially identical or whitespace-only edit attempted again.
4. `NO_NEW_EVIDENCE`: Diagnostic evidence fingerprint unchanged across cycles.
5. `NONE`: Constructive progress confirmed.
6. `UNKNOWN`: Insufficient evidence to establish reason.

---

## 4. Threshold & Boundary Semantics

- **Single Failure Invariant**: A single failure never triggers `NO_PROGRESS` by itself. The initial failing test establishes a baseline.
- **Configurable Default**: Configured to **2 consecutive materially equivalent unsuccessful cycles**.
- **Streak Accounting**:
  - Cycle 1 (Failure A): Streak = 1 ($< 2$). Status = `PROGRESS` (baseline established).
  - Cycle 2 (Failure A repeated): Streak = 2 ($\ge 2$). Status = `NO_PROGRESS`.
  - Cycle 3 (Progress detected / test passed): Streak resets to 0.

---

## 5. Normalization & Fingerprinting Rules

- **Text Normalization**: Lowercases, removes volatile memory addresses (`0xADDR`), strips line numbers (`:123:`), and collapses punctuation and whitespace.
- **Code Edit Normalization**: Strips per-line leading/trailing whitespace and filters blank lines before hashing.
- **Modified File Normalization**: Sorts normalized relative paths and filters against known relevant source files.
- **Evidence Normalization**: Sorts normalized observation strings to ensure order invariance.

---

## 6. TaskState Integration & Security Hygiene

- State updates call `TaskState.increment_no_progress()` upon `NO_PROGRESS` and `TaskState.reset_no_progress()` upon `PROGRESS`.
- Summaries and observations are strictly bounded (max 500 characters) to prevent context bloat.
- No credentials, API tokens, or secrets are included in snapshots or fingerprints.

---

## 7. Structural Validation Results

### 7.1. Submission Validator Output
```text
=== Validating Submission Directory: experiments\candidates\E10 ===
Total Files Inspected: 4
Total YAML Files:      1
Total Unpacked Size:   24,770 bytes (0.02 MB)
Discovered Models:     ['gemma-4-31b-it-qat-w4a16-ct']

RESULT: PASSED (Schema, single-model rule, and limits verified)
```

### 7.2. SHA-256 Hashes
- **E10 `agent.yaml`**: `779f70c0feeb9f89b577a62c73361afc3aae7823d86a05e23b6fc246b66babf7`
- **E10 `root.md`**: `4766117f671fd7fb4e4e8ade8afe46d7c9412fbe7255ee2a29f9b38ebc25b73f`
- **Canonical `test_strategy/SKILL.md`**: `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148` (Invariant)
- **Canonical `repo_triage/SKILL.md`**: `ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce` (Invariant)
- **Parent E9 `root.md`**: `a03fba7410c03d0929d95653ad892c42f802d2a0a017eab92a2e2168bee2fc48`

---

## 8. Anti-Fabrication Disclosures

In strict adherence to `AGENTS.md`:
1. **No Live Gemma Inference**: Candidate E10 has not been executed against live Gemma 4 inference on this workstation.
2. **No Official Benchmark Execution**: Benchmark evaluation has not been executed for E10.
3. **No Pass Rate Claim**: `pass_rate: null`, `no_progress_detection_accuracy: null`.
4. **No Performance Claims**: No claim is asserted that no-progress detection improves pass rates until empirical measurements on official competition platforms demonstrate it.
5. **No Stage 20+ Features**: Recovery paths, rollback actions, sub-agents (Scout, Debugger, Reviewer), and LoRA adapters are strictly excluded.
