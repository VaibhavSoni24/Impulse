# Experiment Report — Prompt Candidate IMPULSE-E1

**Experiment ID:** EXP-PROMPT-E1  
**Candidate Identifier:** `E1`  
**Parent Candidate:** `E0` (Git commit: `99c0da320af4940f4eca27d172592d1ed706d26f`, Tag: `E0-baseline`)  
**Date:** 2026-09-26  
**Status:** Candidate Defined / Pending Live Model Inference  
**Evidence Status:** Hypothesis Only (Unvalidated)  
**Authoritative References:** [PLAN.md](file:///E:/Projects/Impulse/PLAN.md) (Section 12, Stage 10), [manifest.json](file:///E:/Projects/Impulse/experiments/prompts/E1/manifest.json)

---

## 1. Why E1 Exists

Candidate E1 is the first prompt-engineering ablation of the IMPULSE project. In accordance with **PLAN.md Stage 10**, each iteration must isolate a single deliberate intervention against the frozen baseline (`E0`) without altering tools, model weights, decoding hyper-parameters, or execution environments.

Because the local development environment lacks the physical GPU hardware (4× NVIDIA L4) required to run live model inference for `gemma-4-31b-it-qat-w4a16-ct`, Stage 8 established an `execution_unavailable_local_host` baseline record. Consequently, **E1 is NOT based on an empirically observed failure trace**; instead, it targets a structural operational risk identified through inspection of the baseline E0 prompt.

---

## 2. Behavioral Requirement Comparison & Rationale

| Dimension | Frozen Baseline (`E0`) | Prompt Candidate (`E1`) |
|---|---|---|
| **Pre-Edit Behavior** | Step 4 inspects context, followed directly by Step 5 applying edits (`edit_file` / `write_file`). | Step 4 inspects context; Step 5 mandates an explicit, evidence-backed root cause hypothesis before editing. |
| **Reason for Change** | Software engineering models frequently jump to speculative code modifications immediately upon finding symbol matches, without articulating the causal bug mechanism. | Requiring an explicit root cause hypothesis compels the model's high-budget thinking stream to verify the failure mechanism before modifying files. |
| **Operational Impact** | Risk of premature code modifications and turn-budget waste on non-viable patches. | Targeted at reducing speculative edits and improving first-attempt patch accuracy. |

---

## 3. Exact Prompt Delta (E0 → E1)

The single prompt intervention between `agent/prompts/root.md` (E0) and `experiments/candidates/E1/prompts/root.md` (E1) is the insertion of Step 5:

```diff
  4. **Inspect Candidate Context**: Read the candidate source files and examine surrounding code context to understand invariants and existing conventions.
+ 5. **Formulate Root Cause Hypothesis**: Before applying any code modifications, articulate an explicit, evidence-backed hypothesis identifying the root cause of the issue and the exact expected behavioral fix.
- 5. **Make the Smallest Justified Change**: Apply the minimal necessary modification directly to the source implementation files using `edit_file` or `write_file`. Do not perform unrelated refactoring.
+ 6. **Make the Smallest Justified Change**: Apply the minimal necessary modification directly to the source implementation files using `edit_file` or `write_file`. Do not perform unrelated refactoring.
- 6. **Run Targeted Verification**: Execute a targeted test for the modified component using `run_command` (e.g., `pytest tests/path/to/test_file.py -k test_name`). Avoid running full-repository test sweeps without a target file, as they can cause timeouts.
+ 7. **Run Targeted Verification**: Execute a targeted test for the modified component using `run_command` (e.g., `pytest tests/path/to/test_file.py -k test_name`). Avoid running full-repository test sweeps without a target file, as they can cause timeouts.
- 7. **Address Failures Iteratively**: If targeted verification reveals issues, inspect test output, diagnose the failure, and apply follow-up fixes when justified.
+ 8. **Address Failures Iteratively**: If targeted verification reveals issues, inspect test output, diagnose the failure, and apply follow-up fixes when justified.
- 8. **Review the Final Diff**: Inspect repository changes to ensure that only intended source files are modified, no scratch files remain in the working tree, and the patch is clean.
+ 9. **Review the Final Diff**: Inspect repository changes to ensure that only intended source files are modified, no scratch files remain in the working tree, and the patch is clean.
- 9. **Submit Patch**: Call `submit_patch` once the fix is verified and ready.
+ 10. **Submit Patch**: Call `submit_patch` once the fix is verified and ready.
```

**Zero Other Changes:** The agent configuration (`experiments/candidates/E1/agent.yaml`) preserves the exact model (`gemma-4-31b-it-qat-w4a16-ct`), sampling parameters (`temperature: 0.2`, `top_p: 0.95`, `max_output_tokens: 16384`, `thinking_level: high`, `thinking_budget: 4096`), tool declarations (6 tools), and directory boundaries.

---

## 4. Hypothesis Specification

- **Primary Hypothesis:** Forcing the agent to explicitly state a concise, evidence-backed hypothesis regarding root cause and expected behavior before invoking file modification tools will reduce turn waste on ungrounded edits and improve task localization accuracy.
- **Measurable Metrics for Future Validation:**
  1. **Pass Rate:** $\text{pass\_rate}(E1) \ge \text{pass\_rate}(E0)$
  2. **Average Tool Calls:** Tool calls spent on non-viable edits prior to first passing test run will decrease.
  3. **Diff Cleanliness:** Fewer files modified per task run.

---

## 5. Current Evidence vs. Missing Evidence

### 5.1. What Currently Exists
- Structural and syntactic validity of the E1 candidate specification (`agent.yaml`, `prompts/root.md`).
- Exact cryptographic tracking (SHA-256 hashes) linking E1 to parent baseline E0.
- Orchestration compatibility with `local.runner` and `local.evaluation`.

### 5.2. What Is Missing
- **Live Model Generations:** Zero tokens have been generated by `gemma-4-31b-it-qat-w4a16-ct` for E1 because the required 4× NVIDIA L4 GPU vLLM cluster is unavailable locally.
- **Empirical Task Outcomes:** Zero pass/fail results exist.
- **Performance Conclusion:** **No conclusion regarding E1 superiority or viability has been made or can be asserted at this stage.**

---

## 6. Planned Comparison Against E0

Once a remote GPU execution environment is provisioned:
1. Both E0 and E1 will be executed against the identical 5-task smoke set ([`benchmark/tasks/smoke.jsonl`](file:///E:/Projects/Impulse/benchmark/tasks/smoke.jsonl)).
2. Empirical metrics (`resolved`, `tool_calls`, `turns`, `elapsed_seconds`) will be recorded in `local.evaluation` database.
3. E1 will be retained only if empirical pass rate or tool efficiency improves upon E0 without introducing regressions.
