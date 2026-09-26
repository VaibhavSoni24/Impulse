# ADR: Failure Classification Mechanism (Candidate E9 / Stage 18)

**Status:** Approved  
**Date:** 2026-09-26  
**Parent Candidate:** Candidate E8 (`a3a86b0702895dce84093219e2279301a1e53d1d`)  
**Scope:** Stage 18 of PLAN.md

---

## 1. Context and Problem Statement

During autonomous repository-level defect repair, test verification failures frequently occur. In unguided agent systems, failures often trigger blind, repetitive edits:
- Modifying source code in response to a malformed command invocation or missing environment dependency.
- Repeating an edit because a failure was pre-existing in baseline repository behavior.
- Retrying an identical failed hypothesis across multiple turns without diagnosing whether the hypothesis itself was refuted.
- Over-generalizing an edge-case test failure into an invalid rewrite of core logic.

To prevent wasteful retry loops and misdiagnosed errors, PLAN.md Stage 18 requires establishing an explicit failure classification mechanism:
$$\text{Test Failure} \longrightarrow \text{Evidence Inspection} \longrightarrow \text{Failure Classification} \longrightarrow \text{TaskState Recording}$$

Stage 18 isolates the question: **"What kind of failure just occurred?"**  
It explicitly defers:
- **"Is the agent repeating itself without progress?"** (Stage 19: No-Progress Detector)
- **"What corrective path should be taken?"** (Stage 20: Recovery Paths)

---

## 2. The Eight Canonical Failure Categories

Failure classification defines exactly eight machine-readable categories:

| Category | Identifier | Evidence Criterion |
| :--- | :--- | :--- |
| **Environment** | `ENVIRONMENT` | Failure caused by host environment constraints (missing runtime, missing package/dependency, unavailable toolchain binary, permission error). |
| **Command** | `COMMAND` | Invocation syntax error, invalid CLI flags, malformed options, or incorrect test-selection syntax. |
| **Pre-Existing Failure** | `PRE_EXISTING_FAILURE` | Baseline verification demonstrated that the failure already existed prior to any code modification. |
| **Regression** | `REGRESSION` | Behavior that passed during baseline execution is broken by the current patch. |
| **Incomplete Fix** | `INCOMPLETE_FIX` | Fix aligns with root-cause hypothesis, but verification reveals unfulfilled secondary assertions or edge branches. |
| **Wrong Hypothesis** | `WRONG_HYPOTHESIS` | Error traceback or source evidence directly contradicts the assumed root cause or points to an unrelated component. |
| **New Edge Case** | `NEW_EDGE_CASE` | Primary fix succeeds, but novel boundary condition, empty input, or extreme value exposes an unhandled edge. |
| **Unknown** | `UNKNOWN` | Available diagnostic signals are insufficient, ambiguous, or conflicting. |

---

## 3. Category Boundaries & Confusion Prevention

To prevent misclassification, explicit boundaries are enforced:

1. **`COMMAND` vs. `ENVIRONMENT`**:
   - `COMMAND`: The binary exists and executes, but command-line syntax, arguments, or options are rejected (e.g., `pytest: error: unrecognized arguments`, syntax error).
   - `ENVIRONMENT`: The command cannot execute due to missing binaries (`command not found: pytest`), missing Python packages (`ModuleNotFoundError`), or OS permissions (`PermissionError: [Errno 13]`).

2. **`PRE_EXISTING_FAILURE` vs. `REGRESSION`**:
   - `PRE_EXISTING_FAILURE`: Baseline run records `FAILED` on this test prior to patch application.
   - `REGRESSION`: Baseline run records `PASSED` on this test; post-patch run fails.

3. **`INCOMPLETE_FIX` vs. `WRONG_HYPOTHESIS`**:
   - `INCOMPLETE_FIX`: Core assertions pass or improve; failure is confined to secondary expectations within the hypothesized module.
   - `WRONG_HYPOTHESIS`: Stack trace originates in an unaddressed component, or the failure is completely unchanged despite verifying the hypothesized cause was addressed.

4. **`REGRESSION` vs. `NEW_EDGE_CASE`**:
   - `REGRESSION`: Existing baseline tests break after code edits.
   - `NEW_EDGE_CASE`: A newly added or previously unexercised boundary condition test fails while primary baseline tests remain green.

5. **`NEW_EDGE_CASE` vs. `UNKNOWN`**:
   - `NEW_EDGE_CASE`: Boundary keywords, boundary values, or explicit edge assertions fail.
   - `UNKNOWN`: Insufficient evidence to determine causality.

---

## 4. Deterministic Classification Priority Order

The deterministic classifier (`FailureClassifierV1`) evaluates signals in a strict, reproducible sequence:

1. **Step 1: COMMAND**: Inspect combined stdout/stderr for invalid argument patterns, usage messages, or syntax errors.
2. **Step 2: ENVIRONMENT**: Inspect output for missing packages (`ModuleNotFoundError`, `ImportError`), missing binaries, or permission errors.
3. **Step 3: PRE_EXISTING_FAILURE**: Check baseline execution status (`baseline_result == "FAILED"`).
4. **Step 4: REGRESSION**: Check baseline status (`baseline_result == "PASSED"`) with post-patch failure.
5. **Step 5: INCOMPLETE_FIX**: Check for partial passes or secondary assertion failures within targeted components.
6. **Step 6: WRONG_HYPOTHESIS**: Check if failure persists outside modified files or refutes the causal mechanism.
7. **Step 7: NEW_EDGE_CASE**: Check for boundary keywords and edge condition inputs.
8. **Step 8: UNKNOWN**: Fall back to `UNKNOWN` whenever signals are incomplete.

---

## 5. TaskState Integration & Security Hygiene

- **Schema Re-use**: Classification records map directly into existing `TaskState.failures` using `TaskState.add_failure()`. No parallel database or schema revisions are required.
- **Log Bounding**: Raw stdout/stderr and tracebacks are truncated to bounded snippets (max 1000 characters) to prevent context explosion.
- **Zero Secrets**: Credentials, tokens, session IDs, and secret environment variables are never stored in classification context or task state.

---

## 6. Prompt-Guided Fallback

In the root agent prompt (`experiments/candidates/E9/prompts/root.md`):
- Whenever meaningful test verification fails, the agent must explicitly inspect failure evidence and select one of the eight canonical classes.
- The prompt explicitly requires evidence-backed rationales and instructs the agent to select `UNKNOWN` if evidence is ambiguous.
- The prompt does **not** prescribe recovery actions or repetition limits.

---

## 7. Experimental Hypothesis & Future Metrics

### Hypothesis
Requiring the agent to explicitly classify test verification failures using a structured eight-category taxonomy before taking follow-up action will reduce repeated incorrect edits, prevent mistaking environment errors for code defects, and improve diagnostic accuracy.

### Future Metrics (Unasserted at Stage 18)
- `classification_accuracy`
- `repeated_bad_edit_count`
- `same_hypothesis_repeat_count`
- `pass_rate` (null at Stage 18)

---

## 8. Explicit Stage Boundaries (Hard Stop)

Candidate E9 implements **Stage 18 only**.
- **Stage 19 (No-Progress Detector)** is NOT implemented. No repetition counters or loop-breaking triggers exist.
- **Stage 20 (Recovery Paths)** is NOT implemented. No automatic rollback or search fallbacks exist.
- Sub-agents, LoRA adapters, and packaging optimizations remain strictly excluded.
