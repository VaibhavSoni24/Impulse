# ADR: Scout Specialist Agent Architecture (Stage 21)

**Status:** Approved  
**Date:** 2026-09-28  
**Parent Candidate:** Candidate E11 (`70679eb7680be0867e5edf8c18a8f89cb0ea583d`)  
**Scope:** Stage 21 of PLAN.md (First Specialist Agent)

---

## 1. Context and Problem Statement

In repository-level issue resolution, initial localization of defect candidates is often ambiguous. While the root agent possesses general reasoning, hybrid retrieval, failure classification, no-progress detection, and bounded recovery, broad exploration by the root agent consumes significant context and can risk premature edits based on weak candidates.

Stage 21 introduces IMPULSE's first specialist: the **Scout Agent**.

The purpose of Scout is strictly read-only repository localization and candidate evidence gathering. Scout investigates the codebase, traces symbols and relationships, and reports structured findings back to the root agent. Scout is **not** an editor, debugger, reviewer, or recovery controller. Its responsibility concludes upon returning structured localization evidence.

---

## 2. Why Scout Is Strictly Read-Only

Allowing sub-agents to mutate workspace state introduces major failure modes:
1. Multi-agent edit collisions and fragmented patch history.
2. Inability to isolate responsibility for regressions or syntax breaks.
3. Uncontrolled file creation and violation of change-ownership invariants.

By making Scout strictly read-only:
- **Structural Safety**: Scout cannot alter source files, create files, submit patches, or execute destructive shell commands.
- **Evidence-Only Invariant**: Scout's outputs are empirical observations and hypotheses for the root agent to independently verify.
- **Auditable Boundary**: The root agent maintains exclusive ownership over the working tree and patch submission.

---

## 3. Scout Tool Subset

Scout is provided with the minimal necessary non-mutating competition tools:
- `read_file`: Inspect candidate implementation and test files directly.
- `get_status`: Inspect git status and workspace structure.
- `search_similar_code`: Selectively query semantic code similarity.
- `get_code_neighbors`: Query relational graph neighbors (callers, callees, definitions).
- `get_code_subgraph`: Query small subgraphs connecting interacting symbols.

### Excluded Tools
- `edit_file` (mutation forbidden)
- `write_file` (mutation forbidden)
- `submit_patch` (submission reserved for root)
- `run_command` (arbitrary shell execution forbidden; prevents destructive commands)

---

## 4. Structured Scout Output Contract

Scout produces a bounded, structured output represented by `ScoutResult`:
- `issue_summary`: Concise summary of the identified issue mechanism.
- `candidate_files`: List of suspect source files.
- `candidate_symbols`: List of relevant functions, classes, or variables.
- `relevant_relationships`: Discovered caller/callee or architectural relationships.
- `evidence`: Concrete observations referencing observed code lines.
- `unresolved_questions`: Remaining ambiguities or areas requiring verification.
- `recommended_inspection_targets`: Specific locations the root agent should inspect.
- `status`: One of four categorical outcomes:
  - `LOCALIZED`: Defect definitively pinpointed to specific symbols/files.
  - `PARTIALLY_LOCALIZED`: Subsystem or module identified, but exact defect symbol remains ambiguous.
  - `AMBIGUOUS`: Multiple conflicting candidates exist.
  - `INSUFFICIENT_EVIDENCE`: Clues insufficient to establish credible candidates.

---

## 5. Deterministic Uncertainty Trigger Definition

Scout invocation is governed by an explicit deterministic condition:
$$\text{SCOUT\_TRIGGER} = \text{True}$$
Trigger conditions require that:
1. **Initial Reconnaissance Completed**: Cheap direct reconnaissance (triage, exact search) has already occurred (`exact_recon_completed == True`).
2. **Defect Not Yet Confirmed**: Source evidence is not yet sufficient and defect location is unconfirmed (`not has_confirmed_defect_location` and `not source_evidence_sufficient`).
3. **Pre-Edit Phase**: The root agent has not yet committed to an edit hypothesis (`not has_committed_edit_hypothesis`).
4. **Ambiguity Persists**:
   - Multiple candidate files or symbols remain unresolved (`len(candidate_files) > 1`), OR
   - Zero candidates established despite reconnaissance (`len(candidate_files) == 0`), OR
   - Semantic/graph retrieval returned weak or conflicting evidence (`retrieval_conflicting_or_weak == True`).

Scout is **never** triggered merely because a test failed, a task is difficult, or the repository is large.

---

## 6. Controlled Experiment Design: E_S1 vs. E_S2

To rigorously determine whether Scout improves localization enough to justify its extra model calls, Stage 21 defines two isolated candidates holding all other factors constant:

| Attribute | Candidate E_S1 | Candidate E_S2 |
| :--- | :--- | :--- |
| **Concept** | Root + Scout Available | Root + Scout Mandatory under Uncertainty |
| **Invocation Policy** | Discretionary (Root agent decides if information gain justifies the call) | Mandatory (Root agent must invoke Scout once when uncertainty fires) |
| **Scout Config** | Identical (`agent/sub_agents/scout.yaml`) | Identical (`agent/sub_agents/scout.yaml`) |
| **Scout Prompt** | Identical (`agent/prompts/scout.md`) | Identical (`agent/prompts/scout.md`) |
| **Scout Model** | `gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` |
| **Scout Tools** | 5 read-only tools | 5 read-only tools |
| **Root Model & Tools** | `gemma-4-31b-it-qat-w4a16-ct`, 9 competition tools | `gemma-4-31b-it-qat-w4a16-ct`, 9 competition tools |
| **Skills** | `test_strategy`, `repo_triage` | `test_strategy`, `repo_triage` |

This experimental isolation ensures that differences in downstream performance isolate the invocation policy without confounding changes.

---

## 7. Loop-Prevention Policy

To eliminate recursion and infinite invocation loops:
- **Maximum 1 Invocation Per Episode**: Scout may be invoked at most once per unchanged uncertainty episode (`prior_scout_invocations == 0` for the current repository state version).
- **No Repeat on Ambiguity**: If Scout returns `AMBIGUOUS` or `INSUFFICIENT_EVIDENCE`, the root agent does not call Scout again with the same context. It must proceed using root recovery or exact reading.
- **Repository State Progression**: A subsequent Scout invocation is permitted only if the repository state version materially advances (e.g., following a new code modification or diagnostic cycle).

---

## 8. TaskState Integration & Security Hygiene

- **Evidence Recording**: Findings are incorporated via `ScoutResult.integrate_into_task_state(state)`, which registers candidate locations and adds evidence observations attributed to `source="scout_agent"`.
- **Log Bounding**: Observations and summaries are truncated (`MAX_SUMMARY_LEN = 500`) to prevent context bloat.
- **Zero Secrets**: Credentials, API tokens, and secret environment variables are never included in Scout outputs.
- **Anti-Overfitting**: Scout prompts and configs contain zero benchmark instance IDs, hardcoded file targets, or precomputed solution snippets.

---

## 9. Expected Information Value & Future Metrics

### Expected Information Value
Scout is expected to narrow candidate search spaces in complex multi-module repositories, reducing the number of invalid or exploratory edits made by the root agent.

### Empirical Metrics (Unasserted at Stage 21)
- `localization_accuracy_at_k`
- `turns_to_first_correct_candidate`
- `scout_call_frequency`
- `incremental_cost_per_localization`
- `pass_rate` (null at Stage 21)

---

## 10. Explicit Stage Boundary (Hard Stop)

Candidate E_S1 and E_S2 implement **Stage 21 only**.
- **Stage 22 (Debugger Agent)** is NOT implemented.
- **Stage 23 (Reviewer Agent)** is NOT implemented.
- Multi-agent topology experiments, context compaction, and LoRA adapters remain strictly excluded.
