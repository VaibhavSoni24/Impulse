# Candidate E9 Experiment Report: Failure Classification

**Candidate ID:** E9  
**Parent Candidate:** E8  
**Parent Git Commit:** `a3a86b0702895dce84093219e2279301a1e53d1d`  
**Date:** 2026-09-26  
**Status:** Validated (Structural validation only; execution unasserted)

---

## 1. Motivation and Purpose (Stage 18)

In autonomous software repair, test verification failures frequently lead agents into unproductive loops:
- Treating command syntax errors or environment dependency errors as code defects, prompting invalid code modifications.
- Retrying identical failing edits without recognizing that the failure pre-existed in repository baseline.
- Repeating refuted hypotheses across multiple turns.
- Over-generalizing an unconsidered edge case into a destructive rewrite of core working logic.

Stage 18 establishes a structured failure classification mechanism. Whenever meaningful verification fails, the failure must be explicitly categorized before attempting follow-up actions.

---

## 2. E8 → E9 Architecture Delta

```text
Candidate E8 (Stage 17):
  Model: gemma-4-31b-it-qat-w4a16-ct
  Tools: 9 competition tools
  Skills: [skills/test_strategy, skills/repo_triage]
  Policy: Bounded repository triage reconnaissance + hybrid localization + testing strategy

Candidate E9 (Stage 18):
  Model: gemma-4-31b-it-qat-w4a16-ct (Preserved identical)
  Tools: 9 competition tools (Preserved identical)
  Skills: [skills/test_strategy, skills/repo_triage] (Preserved identical)
  Delta: Added 8-class failure taxonomy and deterministic classifier (FailureClassifierV1),
         prompt instruction requiring explicit classification after test failures,
         and structured recording into TaskState.failures.
```

---

## 3. The Eight Failure Categories & Boundaries

The classification system defines eight canonical categories:
1. `ENVIRONMENT`: Failure due to host constraints (missing Python packages, missing toolchain binaries, permission errors).
2. `COMMAND`: Invalid invocation syntax, unrecognized CLI options, malformed flags, or incorrect test-selection syntax.
3. `PRE_EXISTING_FAILURE`: Test was already failing in baseline verification prior to any code modification.
4. `REGRESSION`: Test passed during baseline run, but failed after changes were introduced.
5. `INCOMPLETE_FIX`: Core hypothesis is plausible, but verification reveals unfulfilled secondary assertions or edge branches.
6. `WRONG_HYPOTHESIS`: Error traceback or source evidence directly contradicts the assumed root cause or points to an unrelated component.
7. `NEW_EDGE_CASE`: Core fix functional, but an unconsidered boundary condition or edge input fails.
8. `UNKNOWN`: Diagnostic signals are insufficient, ambiguous, or conflicting.

---

## 4. Deterministic Classifier Architecture

`FailureClassifierV1` evaluates observable context in a fixed, reproducible sequence:
1. `COMMAND` (syntax/argument errors detected)
2. `ENVIRONMENT` (missing packages, runtimes, permissions)
3. `PRE_EXISTING_FAILURE` (baseline result was FAILED)
4. `REGRESSION` (baseline result was PASSED, post-patch failed)
5. `INCOMPLETE_FIX` (partial progress / secondary assertion failure in target scope)
6. `WRONG_HYPOTHESIS` (traceback in unrelated module, or failure refutes hypothesis)
7. `NEW_EDGE_CASE` (boundary/edge keywords and assertions triggered)
8. `UNKNOWN` (insufficient evidence fallback)

---

## 5. TaskState Integration & Security Hygiene

- Diagnoses map directly into `TaskState.failures` via `state.add_failure()`.
- Snippets and tracebacks are strictly truncated to prevent context bloat (max 1000 characters).
- No credentials, tokens, or secret environment variables are permitted in classification records.
- No secondary failure database is introduced.

---

## 6. Structural Validation Results

### 6.1. Submission Validator Output
```text
=== Validating Submission Directory: experiments\candidates\E9 ===
Total Files Inspected: 4
Total YAML Files:      1
Total Unpacked Size:   24,009 bytes (0.02 MB)
Discovered Models:     ['gemma-4-31b-it-qat-w4a16-ct']

RESULT: PASSED (Schema, single-model rule, and limits verified)
```

### 6.2. SHA-256 Hashes
- **E9 `agent.yaml`**: `eba7d0f032fa169918e2e3e1a1606ead98d1d825688db2817625922dd5ecc977`
- **E9 `root.md`**: `a03fba7410c03d0929d95653ad892c42f802d2a0a017eab92a2e2168bee2fc48`
- **Canonical `test_strategy/SKILL.md`**: `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148` (Invariant)
- **Canonical `repo_triage/SKILL.md`**: `ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce` (Invariant)
- **Parent E8 `root.md`**: `d607c494fc32f3132df3301bccc693adf8ba4074bdbc190860b1df65b6f78220`

---

## 7. Anti-Fabrication Disclosures

In strict adherence to `AGENTS.md`:
1. **No Live Gemma Inference**: Candidate E9 has not been executed against live Gemma 4 inference on this workstation.
2. **No Official Benchmark Execution**: Benchmark evaluation has not been executed for E9.
3. **No Pass Rate Claim**: `pass_rate: null`, `classification_accuracy: null`.
4. **No Performance Claims**: No claim is asserted that failure classification reduces repeated bad edits until empirical measurements on official competition platforms demonstrate it.
5. **No Stage 19+ Features**: No-progress detection (Stage 19) and recovery paths (Stage 20) are strictly excluded.
