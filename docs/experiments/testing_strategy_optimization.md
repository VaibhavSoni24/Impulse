# IMPULSE — Testing Strategy Optimization Loop (Stage 34)

This document establishes the architecture, policy specifications, execution framework, and evaluation standards for the **Testing Strategy Optimization Loop** in IMPULSE.

---

## 1. Purpose & Guiding Principle

The central research and engineering question of Stage 34 is:

> *“Which test-selection strategy provides the most useful evidence about a candidate change at acceptable execution cost?”*

In autonomous software-engineering agents, the goal is neither to "run minimum tests" (which leads to false confidence and hidden regressions) nor to "blindly run all tests" (which causes timeout pathologies, massive tool call exhaustion, and excessive cost).

Instead, the objective is:

$$\text{Maximum Useful Validation Evidence at Acceptable Execution Cost}$$

Stage 34 establishes an empirical, reproducible framework to compare controlled testing variants (**T0 through T3**) on both **Validation Quality** and **Execution Cost**, while maintaining strict single-dimension isolation from prompts, retrieval policies, multi-agent topologies, and frozen skill artifacts.

---

## 2. Core Testing Strategy Variants (T0–T3)

The testing experiment family is defined by PLAN.md:

### T0 — Minimal Targeted Test (Baseline)
- **Concept:** Identifies and executes the single most relevant test covering the modified functions, classes, or files.
- **Enabled Levels:** `TARGETED` only. `ADJACENT`, `SUBSYSTEM`, and `FULL` are disabled.
- **Role:** Pure minimal control baseline against which all broader escalation strategies are evaluated.
- **Execution Budget:** Maximum 2 test commands, 20 test cases, 120s runtime budget.

### T1 — Targeted + Adjacent Tests
- **Concept:** Extends targeted testing by additionally executing tests in the immediate vicinity of changed code (same module, same test class, or sibling unit tests).
- **Enabled Levels:** `TARGETED` and `ADJACENT`.
- **Selection Basis:** Direct module/package adjacency or caller-callee neighborhood determined by repository test discovery.
- **Hypothesis:** Adjacent tests catch side-effects and incomplete fixes introduced during patch synthesis with modest additional runtime.
- **Execution Budget:** Maximum 4 test commands, 40 test cases, 180s runtime budget.

### T2 — Targeted + Subsystem + Full Suite When Feasible
- **Concept:** More aggressive verification that tests across the affected subsystem and conditionally escalates to the full test suite when feasible.
- **Enabled Levels:** `TARGETED`, `ADJACENT`, `SUBSYSTEM`, and `FULL` (conditional).
- **Feasibility Evaluator:** Full suite execution is governed by an explicit, deterministic evaluator that checks historical test runtimes, remaining budget, total suite size, and environment stability. If infeasible, execution terminates cleanly at the subsystem level.
- **Execution Budget:** Maximum 6 test commands, 80 test cases, 300s runtime budget.

### T3 — Adaptive Escalation Based on Failure Risk
- **Concept:** Dynamic, evidence-driven test execution ladder governed by observable risk signals:
  $$\text{TARGETED} \longrightarrow \text{Evaluate Evidence \& Risk} \longrightarrow \begin{cases} \text{Pass + Low Risk} \longrightarrow \text{STOP (Early)} \\ \text{Failure or High Risk} \longrightarrow \text{ADJACENT} \end{cases}$$
  $$\text{ADJACENT} \longrightarrow \text{Evaluate Evidence \& Risk} \longrightarrow \begin{cases} \text{Pass + Resolved} \longrightarrow \text{STOP} \\ \text{Remaining Risk} \longrightarrow \text{SUBSYSTEM} \end{cases}$$
  $$\text{SUBSYSTEM} \longrightarrow \text{Evaluate Feasibility} \longrightarrow \begin{cases} \text{Feasible \& Broad Risk} \longrightarrow \text{FULL SUITE} \\ \text{Otherwise} \longrightarrow \text{STOP} \end{cases}$$
- **Determinism:** The escalation and stopping decisions are completely deterministic functions of observable facts (diff size, file count, API surface changes, test outcomes), strictly avoiding hidden chain-of-thought or opaque probability scores.

---

## 3. Test-Level Hierarchy

Test execution strictly respects the ordered ladder:

| Test Level | Scope | Example | Selection Mechanism |
| :--- | :--- | :--- | :--- |
| `TARGETED` | Modified function / unit test | `pytest tests/test_core.py -k test_parse` | AST & file-level match |
| `ADJACENT` | Same module / sibling test cases | `pytest tests/test_core.py` | Sibling file / class match |
| `SUBSYSTEM` | Feature package / subsystem suite | `pytest tests/model_fields/` | Directory / package root match |
| `FULL` | Complete repository test suite | `pytest tests/` | Full repository test suite |

---

## 4. Observable Risk Signals

T3 utilizes explicit, verifiable risk signals rather than arbitrary neural heuristics:

1. `TARGETED_TEST_FAILED`: Primary targeted test did not pass.
2. `MULTIPLE_FILES_CHANGED`: Modification spans $> 1$ file.
3. `PUBLIC_API_CHANGED`: Public method/function signature modified.
4. `SHARED_UTILITY_CHANGED`: Shared core helper or utility modified.
5. `TEST_INFRASTRUCTURE_CHANGED`: Changes to test fixtures or configuration.
6. `DEPENDENCY_CONFIG_CHANGED`: Changes to `pyproject.toml`, `setup.cfg`, etc.
7. `MULTI_PACKAGE_CHANGED`: Changes cross package boundaries.
8. `ADJACENT_TEST_REGRESSION`: Sibling test regressed while targeted test passed.
9. `INCOMPLETE_FIX_CLASSIFICATION`: Prior test failure classified as incomplete fix.
10. `PRE_EXISTING_FAILURE_INVOLVEMENT`: Pre-existing failure in the touched area.
11. `LARGE_DIFF_SIZE`: Diff size exceeds 50 lines.
12. `NO_TARGETED_TEST_FOUND`: Targeted test could not be identified by discovery.
13. `CRITICAL_PATH_NEW_FILE`: New file introduced in a core path.

Each signal is structured as a typed `RiskSignal` recording `signal_type`, `observed`, `severity`, `rationale`, and `evidence_reference`.

---

## 5. Full-Suite Feasibility Evaluator

Before attempting a full-suite execution in T2 or T3, the `FullSuiteFeasibilityEvaluator` computes:

- `FEASIBLE`: Estimated runtime $\le 120\text{s}$, remaining budget $> \text{estimated runtime}$, suite size $\le 200$ tests, environment stable.
- `NOT_FEASIBLE`: Any limit violated (e.g. estimated runtime exceeds ceiling, remaining budget exhausted, unstable environment).
- `UNKNOWN`: Insufficient metrics available. **UNKNOWN is never automatically treated as FEASIBLE.**

---

## 6. Frozen Artifact Invariance & Skill/Policy Separation

Stage 34 strictly distinguishes between:

1. **Test Strategy Skill (`agent/skills/test_strategy/SKILL.md`):**
   - The frozen Stage 24 knowledge artifact defining general instructions and test runner selection knowledge.
   - **MUST REMAIN UNTOUCHED.** Verified against frozen hash: `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148`.
   - Stage 36 is the dedicated Skill Optimization Loop.
2. **Test Execution Policy (`TestPolicy`):**
   - The runtime configuration deciding *how much* testing to execute, escalation triggers, and feasibility rules.
   - Optimized experimentally in Stage 34.
3. **Test Executor:**
   - The runner issuing commands in isolated execution environments.
4. **Test Telemetry:**
   - Structured `TestExecutionEvent` and `AdaptiveEscalationTrace` logging observable outcomes.

All non-testing dimensions remain invariant:
- Root prompt: `P0` (`2360d4bf...`)
- Retrieval policy: `R0` (`3e1b234a...`)
- Topology: `root_only`
- Model: `gemma-4-31b-it-qat-w4a16-ct`

---

## 7. Quantitative Quality and Cost Metrics

### Quality & Evidence Metrics
- **Pass Rate / Failure Rate:** Fraction of resolved tasks.
- **Regressions Caught:** Total failures caught by adjacent, subsystem, or full suite.
- **Incomplete Fixes Caught:** Failures detected on targeted tests.
- **Targeted Behavior Confirmed:** Passing targeted tests validating patch intent.
- **False-Confidence Reduction:** Cases where TARGETED passed but a broader test level caught a real failure.
- **Early Detection Level:** Earliest level (`TARGETED`, `ADJACENT`, `SUBSYSTEM`, `FULL`) at which the final relevant failure was discovered.
- **Clean-Copy Verification:** Strict verification inside isolated fresh workspace.

### Cost Metrics
- **Total Test Commands:** Broken down into targeted, adjacent, subsystem, and full-suite.
- **Total Tests Executed:** Count of individual test cases run.
- **Total Test Runtime:** Duration in milliseconds (mean, median, p95).
- **Test Output Volume:** Raw output bytes before compaction.
- **Repeated Commands & Duplicate Tests:** Inefficient test reruns on unchanged code.
- **Testing Tool-Call Share:** Ratio of testing commands to total agent tool calls.

---

## 8. Stopping Effectiveness & Redundancy Diagnostics

Stage 34 detects and analyzes testing pathologies:
1. **Duplicate Commands:** Exact same test command issued multiple times without intervening code changes.
2. **Duplicate Test Cases:** Test cases executed repeatedly across multiple test invocations.
3. **Reruns Without Edit:** Test suites rerun when git diff shows zero file modifications.
4. **Unnecessary Full Suites:** Full suite executed on low-risk tasks where targeted tests passed.
5. **Zero-New-Evidence Runs:** Adjacent or subsystem runs that discover zero new failures or regressions.
6. **Repeated Failures:** Identical failure reproduced repeatedly without progress.

---

## 9. Failure-Driven Development (FDD) Integration

Testing strategy interventions follow the Stage 31 FDD lifecycle:
1. Failure evidence identified from benchmark evaluations.
2. Causal hypothesis formulated with structured `TestHypothesis`:
   - TARGET FAILURE
   - OBSERVATION
   - HYPOTHESIS
   - TESTING CHANGE
   - EXPECTED SIGNAL
   - REJECTION CONDITION
3. T candidate created and validated for single-dimension integrity.
4. Candidate evaluated on smoke, validation split, and held-out protection.
5. Promotion gate evaluated via `evaluate_promotion_gate(delta)`.

---

## 10. Clean-Copy Evaluator & Stage 25/26 Interactions

- **Clean-Copy Evaluation (Stage 28):** Testing policies evaluate candidates strictly across the clean snapshot $\to$ candidate load $\to$ patch extraction $\to$ fresh snapshot $\to$ apply patch $\to$ verification $\to$ testing lifecycle.
- **Context Compaction (Stage 25):** `compact_test_log` compacts verbose test outputs while guaranteeing preservation of failing test names, assertion lines, and traceback frames.
- **Tool Budgeting (Stage 26):** Testing commands are tracked against runtime budget limits and tool call shares without fabricating invalid cache hits for dynamic test execution.
- **Split Integrity (Stage 29):** Validation split and held-out locks are verified cryptographically. Held-out sets are never used for iterative tuning.

---

## 11. Evidence Modes & Local Host Limitation

Stage 34 enforces strict separation of evidence modes:
- `LIVE`: Grounded in actual Gemma 4 31B inference.
- `FIXTURE`: Deterministic synthetic scenarios (A through Y) for offline verification.
- `INFRASTRUCTURE_ONLY`: Evaluation runs aborted due to host limitations.
- `UNAVAILABLE`: Local baseline state where competition model inference cannot execute locally.

Because the local Windows host lacks competition-scale Gemma 4 31B inference, all canonical candidates T0 through T3 are recorded with `evidence_mode = UNAVAILABLE`. Zero task-solving improvements are fabricated.
