# Recovery Optimization Loop (Stage 35)

## 1. Purpose and Central Question

The **Recovery Optimization Loop** establishes a disciplined, causal, and empirical framework for evaluating and optimizing autonomous recovery behaviors within the **IMPULSE** software engineering agent.

The core question addressed by Stage 35 is:

> *"Can a specific recovery intervention detect and resolve a repeated failure pattern earlier or more reliably, without introducing new loops, unnecessary retries, or collateral regressions?"*

Recovery optimization is emphatically **NOT**:
- "retry more"
- "recover from everything"
- "add more fallback rules"

Instead, every recovery intervention is evaluated against the multi-dimensional frontier:
$$\text{Earlier Detection} + \text{More Reliable Recovery} + \text{Bounded Cost} + \text{No New Loops}$$

---

## 2. Invariance and Single-Dimension Discipline

During Stage 35 recovery experiments, all non-recovery subsystems remain strictly invariant:

- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct` (Invariant)
- **Root Prompt:** P0 baseline SHA-256 `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e` (Invariant, unless an isolated recovery-specific prompt instruction is tested under `InterventionScope.RECOVERY`)
- **Retrieval Policy:** Canonical R0 SHA-256 `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7` (Invariant)
- **Testing Strategy:** Canonical T0 SHA-256 `76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36` (Invariant)
- **Topology:** `root_only` (Invariant)
- **Specialists:** Scout, Debugger, Reviewer configurations (Invariant)
- **Skills:** `test_strategy/SKILL.md` (`3d027b0f...`) and `repo_triage/SKILL.md` (`ac7a9671...`) (Frozen Stage 24 artifacts)
- **Benchmark Splits:** Stage 29 canonical task splits (Invariant)

Any experiment that simultaneously mutates prompt, retrieval, testing, topology, or skills is rejected as invalid.

---

## 3. Recovery Failure Pattern Mining

The recovery analysis engine (`local.recovery_opt.mining.RecoveryTraceMiner`) deterministically inspects authoritative execution records:
- SQLite evaluation database (`experiments/evaluation.db`)
- Normalized failure records (`failures`)
- Run event sequences (`run_events`)
- Recovery traces (`recovery_trace.jsonl`)
- Test and tool execution traces

### Observable Pattern Taxonomy
The miner extracts evidence across ten deterministic pattern dimensions:
1. `REPEATED_COMMAND`: Same normalized shell command repeated consecutively with failing outcome.
2. `REPEATED_ERROR`: Same failure signature repeated across turns without evidence change.
3. `REPEATED_EDIT`: Same file or code region repeatedly modified without test progress.
4. `REPEATED_HYPOTHESIS`: Same failure class/hypothesis repeated after unsuccessful recovery attempt.
5. `RECOVERY_THRASHING`: Oscillation between recovery paths (Path A $\rightarrow$ Path B $\rightarrow$ Path A).
6. `RECOVERY_OMISSION`: Known observable failure occurs but no recovery action triggers.
7. `LATE_RECOVERY`: Recovery action eventually executes, but multiple unnecessary iterations elapsed first.
8. `FAILED_RECOVERY`: Recovery executes but fails to change the failure state.
9. `RECOVERY_LOOP`: Recovery rule triggers repeated application without convergence.
10. `RETRY_WASTE`: Multiple identical retries executed despite no change in repository state.

---

## 4. Deterministic Clustering and Selection

Normalized `RecoveryFailureRecord` instances are deterministically grouped into `RecoveryCluster` objects by `(pattern_type, canonical_signature)`.

### Transparent Lexicographic Cluster Selection
Clusters are prioritized without subjective weighting:
1. Eligible completed `LIVE` runs containing the pattern (descending)
2. Unique affected tasks (descending)
3. Recurrence count (descending)
4. Loop count (descending)
5. Recovery failure count (descending)
6. Deterministic `cluster_id` (ascending)

When no actionable `LIVE` recovery pattern exists (e.g. on local host without GPU inference capability), the selector outputs `selection_status = NO_ACTIONABLE_LIVE_RECOVERY`.

---

## 5. Earliest Observable Detection Point

A core requirement of Stage 35 is measuring whether an intervention improves recovery by detecting failures earlier rather than merely altering the terminal action.

The detection lifecycle is tracked across observable milestones:
$$\text{FIRST FAILURE} \longrightarrow \text{FIRST OBSERVABLE OPPORTUNITY} \longrightarrow \text{ACTUAL RECOVERY TRIGGER} \longrightarrow \text{RECOVERY ACTION} \longrightarrow \text{OUTCOME}$$

Metrics:
- `detection_latency_events` $= \max(0, \text{actual\_trigger\_event} - \text{first\_opportunity\_event})$
- `detection_latency_turns` $= \max(0, \text{actual\_trigger\_turn} - \text{first\_opportunity\_turn})$

---

## 6. Recovery State Machine and Actions

The recovery lifecycle transitions through well-defined, bounded states:
$$\text{FAILURE\_DETECTED} \longrightarrow \text{RECOVERY\_ELIGIBLE} \longrightarrow \text{RECOVERY\_SELECTED} \longrightarrow \text{RECOVERY\_EXECUTED} \longrightarrow \text{RESULT\_OBSERVED}$$

Subsequent transitions:
- $\longrightarrow \text{RECOVERED}$ (Target failure exited)
- $\longrightarrow \text{RETRY\_ELIGIBLE}$ (Bounded retry within budget)
- $\longrightarrow \text{ALTERNATE\_PATH}$ (Switch to alternate tool/investigation)
- $\longrightarrow \text{STOP\_RECOVERY}$ (Stop condition satisfied)
- $\longrightarrow \text{LOOP\_DETECTED}$ (Loop/oscillation guard fires)
- $\longrightarrow \text{BUDGET\_EXHAUSTED}$ (Retry bounds reached)

### Canonical Action Families (Stage 20 Integration)
- **Bad Edit Recovery:** `INSPECT_DIFF`, `REPAIR_EDIT`, `REVERT_EDIT` (safe agent-owned files only).
- **Test Failure Recovery:** `INSPECT_DIFF`, `INSPECT_STACK`, `REVISE_HYPOTHESIS`.
- **Search Fallback:** Semantic $\rightarrow$ Exact search $\rightarrow$ Tree inspection $\rightarrow$ Graph.
- **Tool Failure Recovery:** Bounded retry $\rightarrow$ `USE_ALTERNATE_TOOL` $\rightarrow$ Terminate path.
- **Budget Pressure Recovery:** `STOP_EXPLORATION` $\rightarrow$ `TARGETED_VALIDATION` $\rightarrow$ `FINAL_REVIEW`.

---

## 7. Loop Protection and Oscillation Guards

To ensure recovery interventions do not degrade agent autonomy, Stage 35 implements strict loop and oscillation detection:

### Observable State Signature
$$\text{Signature} = \text{SHA-256}(\text{failure\_signature} \mid \text{recovery\_action} \mid \text{repo\_fingerprint} \mid \text{attempt\_number})$$

Guards detect:
- Direct loops: Same action repeating with identical failure and no evidence change.
- Oscillations: Alternating recovery actions (A $\rightarrow$ B $\rightarrow$ A $\rightarrow$ B).
- Thrashing: Rapid path switching without state change.

### Mandatory Loop Regression Gate (Section 35)
Every candidate is compared against baseline on total loop count:
$$\text{Candidate Loops } (Y) > \text{Baseline Loops } (X) \implies \mathbf{REJECTED}$$

---

## 8. Retry Budgets and Stop Conditions

Bounded parameters prevent runaway execution:
- `max_same_action_retries`: Maximum consecutive repetitions of an identical action (default: 1-2).
- `max_total_recovery_attempts`: Maximum recovery attempts per task (default: 3-4).
- `max_alternate_paths`: Maximum alternate routes explored (default: 1-3).
- `max_recovery_runtime_seconds`: Bounded runtime allowance (default: 100-120s).
- `max_recovery_tool_calls`: Bounded recovery tool call limit (default: 6-8).

---

## 9. Paired Comparison on the Same Failure Set

Candidate evaluation requires rerunning the **exact same failure set** as baseline.
Transitions are categorized into:
- `FAIL_TO_RECOVERED` (Targeted failure resolved)
- `FAIL_TO_STILL_FAILING` (Failure unresolved)
- `FAIL_TO_DIFFERENT_FAIL` (Failure mode shifted)
- `FAIL_TO_LOOP` (New loop introduced $\rightarrow$ Reject)
- `FAIL_TO_BUDGET_EXHAUSTED` (Budget exhausted)
- `PASS_UNCHANGED` (Control tasks unaffected)

---

## 10. Canonical Recovery Candidates

| Candidate | Name | Key Feature | Retry Bound | Early Detection | Loop Guard |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **REC0** | Canonical Baseline | Stage 20 canonical recovery paths | 2 same / 4 total | Disabled | Attempt counting |
| **REC1** | Early Detection | 1st-recurrence trigger & fast fallback | 1 same / 4 total | Enabled | Standard |
| **REC2** | Alternate Path | Immediate routing to alternate tools/searches | 1 same / 4 total | Enabled | Standard |
| **REC3** | Adaptive Loop Guard | Signature check, oscillation suppression | 1 same / 3 total | Enabled | Active Guard |

---

## 11. Evidence Modes and Local Environment Limitation

Execution modes are strictly isolated:
- `LIVE`: Live competition inference with Gemma 4 31B.
- `FIXTURE`: Deterministic synthetic traces for mechanism verification.
- `INFRASTRUCTURE_ONLY`: Hardware/platform unavailability runs.
- `UNAVAILABLE`: Local execution without required multi-GPU stack.

### Current Local Baseline Reality
Because the local Windows development host lacks 4x NVIDIA L4 GPUs (96 GB VRAM) required for competition-scale 31B inference, live benchmark execution is unavailable locally.
Historical runs in `evaluation.db` are classified as `infrastructure_unavailable`. In accordance with Project Governance (AGENTS.md Section 2 Zero Fabrication), local evaluation reports `NO_ACTIONABLE_LIVE_RECOVERY`. Mechanism validation is established through 31 deterministic fixtures (A through AE) with 100% test pass rate.
