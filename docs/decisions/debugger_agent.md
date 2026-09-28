# Architecture Decision Record: Debugger Specialist Agent (Stage 22)

## Status
ACCEPTED (Stage 22 Implementation)

## Context
Following Stage 21 (Scout specialist for read-only repository localization), IMPULSE requires a mechanism to diagnose non-trivial test failures during the repair cycle. When targeted verification fails, the Root agent must decide whether to adjust its hypothesis, revise specific code blocks, or trigger a recovery path.

In baseline candidates (E0 through E11) and D1, the Root agent performs all post-failure diagnosis unilaterally. While simple assertion failures are easily triaged, complex failures—such as ambiguous call paths, unexpected regressions, subtle edge-case omissions, or uninformative stack traces—can lead to repeated failed edits, thrashing, or exhaustion of recovery bounds.

Stage 22 introduces a dedicated, read-only specialist: the **Debugger Agent**.

---

## Decision

### 1. Purpose of the Debugger Agent
The Debugger investigates meaningful verification failures and produces structured causal diagnostic evidence (`DebuggerResult`) to help the Root agent update its working hypothesis and select the next repair action.

The Debugger answers:
> *"Why did the verification fail, what causal execution path does the evidence indicate, and what concrete code locations should the Root agent inspect next?"*

The Debugger does **NOT**:
- Edit or create source files.
- Submit patches.
- Execute rollbacks or recovery procedures.
- Replace the E9 failure classifier, E10 no-progress detector, or E11 recovery controller.
- Replace the Root agent's authority over repair decisions.

### 2. Distinction Between Scout and Debugger
| Dimension | Scout Specialist (Stage 21) | Debugger Specialist (Stage 22) |
|---|---|---|
| **Primary Question** | "Where is the relevant code?" | "Why did the verification fail?" |
| **Phase of Invocation** | Pre-edit repository reconnaissance & localization | Post-failure diagnostic reasoning |
| **Trigger Condition** | Localization uncertainty (`SCOUT_TRIGGER`) | Difficult verification failure (`DEBUGGER_TRIGGER`) |
| **Input Signals** | Issue statement, symbols, directory layout | Failing test output, stack trace, diff, prior hypothesis |
| **Output Focus** | Candidate files, symbols, relationships | Causal mechanism, contradictions, next inspection targets |

### 3. Read-Only Guarantees and Tool Subset
To eliminate any risk of accidental repository mutation, workspace pollution, or unverified resets, the Debugger is strictly restricted at both configuration and prompt levels:
- **Exposed Read-Only Tools (5 tools)**:
  - `read_file`: Inspect failing test cases, stack trace frames, and source logic.
  - `get_status`: Inspect working tree status without modification.
  - `search_similar_code`: Semantic retrieval for unfamiliar error concepts.
  - `get_code_neighbors`: Examine callers and callees along the execution path.
  - `get_code_subgraph`: Inspect multi-symbol interaction topologies.
- **Prohibited Tools**:
  - `edit_file`, `write_file`, `submit_patch` are completely omitted.
  - `run_command` is omitted from the sub-agent to prevent side-effect commands. The Root agent captures test outputs and provides them to the diagnostic context.
- **Prompt Prohibitions**: The Debugger prompt explicitly forbids file edits, file creation, destructive commands, or patch submissions.

### 4. Deterministic Difficult-Failure Trigger (`DEBUGGER_TRIGGER`)
The Debugger is not invoked after every command or simple failure. It triggers only when:
1. `test_result == 'FAILED'` (a meaningful verification test has failed).
2. Initial direct failure investigation has been completed (`initial_investigation_bounded == True`).
3. The failure is not an ordinary targeted failure with an obvious single fix (`has_clear_single_targeted_fix == False`).
4. At least one explicit diagnostic difficulty condition is present:
   - Failure class is `UNKNOWN`, `WRONG_HYPOTHESIS`, or `INCOMPLETE_FIX`.
   - Failure class is `REGRESSION` with an unclear causal edit.
   - Stack trace / call path is ambiguous or uninformative.
   - Current failure evidence contradicts the previous hypothesis.
   - Multiple plausible causal failure origins remain unresolved.
   - Repeated failure or no-progress is detected across cycles.

### 5. Structured Output Contract (`DebuggerResult`)
The Debugger returns a compact, bounded record avoiding raw log dumps:
- `status`: Categorical outcome (`DIAGNOSED`, `PARTIALLY_DIAGNOSED`, `AMBIGUOUS`, `INSUFFICIENT_EVIDENCE`).
- `failure_class`: Categorization under the 8 canonical E9 classes.
- `failure_summary`: Concise summary of the failure mechanism (max 500 chars).
- `likely_cause_candidates`: Concrete files/symbols implicated.
- `stack_or_call_path_findings`: Bounded trace observations.
- `changed_file_findings`: Observations regarding recent edits.
- `observed_evidence`: Strictly verified observations from tests and source code.
- `inferred_mechanisms`: Plausible causal hypotheses (clearly separated from observations).
- `contradictions`: Specific points where failure contradicts previous working hypothesis.
- `next_inspection_targets`: Specific files/symbols recommended for Root inspection.
- `hypothesis_update`: Recommended revision to the working hypothesis.
- `unresolved_questions`: Remaining ambiguities (max 5 items).

### 6. Subsystem Integration (E9, E10, E11)
- **Failure Classification (E9)**: The Debugger consumes the canonical 8-category taxonomy (`ENVIRONMENT`, `COMMAND`, `PRE_EXISTING_FAILURE`, `REGRESSION`, `INCOMPLETE_FIX`, `WRONG_HYPOTHESIS`, `NEW_EDGE_CASE`, `UNKNOWN`) and enriches evidence without creating a parallel taxonomy.
- **No-Progress Detection (E10)**: Progress status (`PROGRESS`, `NO_PROGRESS`, `INSUFFICIENT_EVIDENCE`) and signals (`REPEATED_FAILURE`, `REPEATED_EDIT`, etc.) feed into `DebuggerTriggerContext`. The Debugger does not maintain duplicate counters.
- **Recovery Paths (E11)**: The recovery subsystem remains strictly downstream. Debugger produces diagnostic evidence; Root updates its hypothesis; E11 recovery controller decides the next recovery action. Debugger cannot execute recovery itself.

### 7. Invocation Bounds and Loop Prevention
- **Episode Bound**: Maximum 1 Debugger invocation per unchanged difficult-failure episode.
- **Suppression Rule**: If Debugger returns `AMBIGUOUS` or `INSUFFICIENT_EVIDENCE`, repeat calls are blocked while repository state version and failure signature remain unchanged.
- **Episode Reset**: A material repository change (new edit applied) or new test execution creating a different failure signature initiates a new episode.

---

## Controlled Experiment Design (D1 vs. D2)

To evaluate whether Debugger-generated evidence justifies its model call cost, Stage 22 isolates invocation policy:

- **Candidate D1 (Root Only)**:
  - Root agent + Scout available.
  - Debugger specialist is **unavailable** (not configured in `agent.yaml`).
  - Root performs all failure triage and recovery directly.
- **Candidate D2 (Root + Debugger)**:
  - Root agent + Scout available + Debugger available.
  - Debugger is invoked under `DEBUGGER_TRIGGER`.

### Controlled Invariants
- Root model: `gemma-4-31b-it-qat-w4a16-ct`.
- Scout model: `gemma-4-31b-it-qat-w4a16-ct`.
- Debugger model: `gemma-4-31b-it-qat-w4a16-ct`.
- Generation settings: `temperature: 0.2`, `top_p: 0.95`, `max_output_tokens: 16384`, `thinking_level: high`, `thinking_budget: 4096`.
- Root tools: Exact 9 competition tools.
- Scout tools: Exact 5 read-only tools.
- Debugger tools: Exact 5 read-only tools.
- Skills: Canonical `test_strategy` and `repo_triage` skills.

---

## Known Limitations & Cost Trade-Offs
1. **Model Call Budget**: Each Debugger invocation incurs additional reasoning and tool tokens. If failures are straightforward, Debugger adds latency without benefit (which `DEBUGGER_TRIGGER` guards against).
2. **Read-Only Scope**: Debugger cannot dynamically inject print statements or run ad-hoc test variations; it relies on static code reading and graph inspection.
3. **Hypothesis Authority**: The Root agent must independently verify Debugger conclusions before applying changes.

---

## Boundary with Stage 23
Stage 22 introduces **only** the Debugger agent. It does **not** implement:
- The Reviewer agent (Stage 23).
- Multi-agent topologies (Stage 24).
- Context compaction (Stage 25).
- Tool-call budgeting (Stage 26).
