# ADR: No-Progress Detection Mechanism (Candidate E10 / Stage 19)

**Status:** Approved  
**Date:** 2026-09-26  
**Parent Candidate:** Candidate E9 (`d8ed92d6c2ff347061aecfdb8068708dc4000be8`)  
**Scope:** Stage 19 of PLAN.md

---

## 1. Context and Problem Statement

In autonomous software engineering agents, defect repair attempts frequently become trapped in non-productive exploration loops:
- Retrying an identical or whitespace-only edit across consecutive turns after test verification fails.
- Pursuing an identical failing root-cause hypothesis repeatedly without discovering new diagnostic evidence.
- Repeatedly invoking identical test commands against an unchanged codebase and expecting a different outcome.
- Wandering across unrelated files while the core defect remains unaddressed.

While Stage 18 introduced **Failure Classification** to diagnose *"What kind of failure just occurred?"*, it did not monitor temporal trajectory across multiple cycles. Stage 19 implements **No-Progress Detection** to answer:
$$\text{"Has the agent stopped making meaningful progress across verification cycles?"}$$

Crucially, Stage 19 isolates detection from reaction:
- **Stage 19 (Current):** Detects and surfaces the no-progress state.
- **Stage 20 (Next):** Implements recovery paths (search fallback, hypothesis revision, edit rollback).

---

## 2. Progress vs. No-Progress Definitions

### Meaningful Progress Signals
A cycle is classified as making meaningful progress if any of the following occur:
1. **Verification Succeeded**: Post-edit verification transitions to `PASSED`.
2. **Failure Class Changed**: The failure classification changes because new evidence emerged (e.g., `COMMAND` $\to$ `REGRESSION`, or `WRONG_HYPOTHESIS` $\to$ `INCOMPLETE_FIX`).
3. **Failing Signature Changed**: The execution path shifted, evidenced by a different failing test name or assertion error.
4. **Hypothesis Revised**: An explicit revision of the root-cause hypothesis was formulated.
5. **Relevant Source Files Changed**: Code modifications targeted relevant implementation components rather than unrelated or documentation files.
6. **New Diagnostic Evidence Recorded**: Genuine new diagnostic observations were added to task state.

### No-Progress Signals
A cycle is classified as lacking progress if:
1. **`REPEATED_FAILURE`**: The exact same failure signature (test name + error message) is reproduced without improvement.
2. **`REPEATED_HYPOTHESIS`**: The identical hypothesis is pursued across consecutive cycles without revision.
3. **`REPEATED_EDIT`**: An identical or whitespace-only code edit is attempted again.
4. **`NO_NEW_EVIDENCE`**: Verification repeated against effectively identical state with zero new diagnostic observations.

---

## 3. Threshold Semantics

- **Threshold Principle**: A single failure must **never** trigger `NO_PROGRESS` by itself. Software defect repair naturally involves initial failing tests during reproduction and hypothesis testing.
- **Configurable Default**: The default threshold is set to **2 consecutive materially equivalent unsuccessful cycles**.
- **Streak Accounting**:
  - Initial failure: Cycle count = 1 ($< \text{threshold}$). Status is `PROGRESS` (baseline established).
  - First repetition: Cycle count = 2 ($\ge \text{threshold}$). Status transitions to `NO_PROGRESS`.
  - Constructive change / pass: Cycle count resets to 0.

---

## 4. Deterministic Fingerprinting & Normalization

Rather than comparing raw string logs (which contain unstable memory addresses, timestamps, or volatile line numbers), `NoProgressDetectorV1` uses normalized fingerprints:
- **Text Normalization**: Strips memory addresses (`0x[0-9a-fA-F]+`), removes dynamic line numbers (`:123:`), strips punctuation, collapses whitespace, and lowercases text.
- **Code Edit Normalization**: Strips per-line leading/trailing whitespace and filters blank lines before hashing.
- **Modified File Normalization**: Sorts normalized, forward-slashed paths and filters against known relevant source files.
- **Evidence Normalization**: Sorts normalized observation strings to ensure order invariance.

---

## 5. TaskState Integration & Security Hygiene

- **State Integration**: No parallel database is created. The assessment updates existing `TaskState.no_progress_count` via `state.increment_no_progress()` and `state.reset_no_progress()`.
- **Log Bounding**: Summary rationale and evidence items are truncated (max 500 characters) to prevent context expansion.
- **Zero Secrets**: Credentials, session tokens, and secret environment variables are never included in fingerprints, snapshots, or progress assessments.

---

## 6. Root Prompt Integration

In `experiments/candidates/E10/prompts/root.md`:
- The agent is instructed to evaluate progress across verification cycles and explicitly record no-progress states in task state.
- The prompt explicitly forbids blindly repeating equivalent failed edits or commands.
- **Hard Boundary**: The prompt does **not** prescribe Stage 20 recovery paths (no rollback commands, no sub-agent delegation, no search fallback algorithms).

---

## 7. Experimental Hypothesis & Future Metrics

### Hypothesis
A deterministic no-progress detector that tracks failure, edit, and hypothesis recurrence across consecutive verification cycles will enable early detection of unproductive loops and prevent repeated invalid edits without prematurely aborting valid exploratory reasoning.

### Future Metrics (Unasserted at Stage 19)
- `no_progress_detection_accuracy`
- `false_positive_no_progress_rate`
- `repeated_bad_edit_reduction_rate`
- `turns_to_loop_detection`
- `pass_rate` (null at Stage 19)

---

## 8. Explicit Stage Boundaries (Hard Stop)

Candidate E10 implements **Stage 19 only**.
- **Stage 20 (Recovery Paths)** is NOT implemented.
- Sub-agents (Scout, Debugger, Reviewer) are NOT implemented.
- Automatic rollback, retry wrappers, and LoRA adapters remain strictly excluded.
