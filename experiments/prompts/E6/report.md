# Experiment Report: Candidate E6 (Hybrid Localization Policy V1)

**Candidate ID:** E6  
**Parent Candidate:** E5  
**Parent Git Commit:** `213195cc97616392da6e69cd3d69e6656ab733a7`  
**Date:** 2026-09-26  
**Status:** Validated (Structural and Policy Testing Only)

---

## 1. Executive Summary & Purpose

Candidate E6 implements **Stage 15 of PLAN.md**, establishing the **Hybrid Localization Policy V1**:
$$\text{E6} = \text{E5} + \text{Hybrid Localization Policy V1}$$

### Why E6 Exists
Candidates E3, E4, and E5 successfully introduced the competition's three retrieval capabilities:
- `search_similar_code` (semantic similarity search)
- `get_code_neighbors` (1-hop relational expansion)
- `get_code_subgraph` (induced multi-symbol subgraphs)

However, making all three tools available without an orchestrating policy risks **indiscriminate or mechanical retrieval chaining** (`search_similar_code` $\to$ `get_code_neighbors` $\to$ `get_code_subgraph`). On the competition platform, where retrieval operations are strictly budget-gated (`@budget_gated(count_tool_call=True)`), indiscriminate retrieval exhausts tool call units, floods the 32,768-token context window with graph payloads, and risks cyclical exploration loops.

E6 solves this by introducing a deterministic, bounded, and auditable controller that decides **which retrieval operation is justified by current evidence** according to an information-gain hierarchy.

---

## 2. E5 $\to$ E6 Architectural Delta

1. **Tool Set Parity**:
   - Zero tools added or removed. All 9 competition tools declared in E5 are strictly preserved (`run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`).
2. **Model & Generation Configuration**:
   - Model remains `gemma-4-31b-it-qat-w4a16-ct`.
   - Temperature (0.2), top_p (0.95), max_output_tokens (16384), and thinking_config (level: high, budget: 4096, include_thoughts: true) are unchanged.
3. **Policy Orchestration**:
   - Introduces `HybridLocalizationPolicy` in `local.retrieval.hybrid_controller`, which composes `RetrievalPolicyV1`, `NeighborPolicyV1`, and `SubgraphPolicyV1`.
   - Establishes explicit decision states (`DecisionState`) and actions (`LocalizationAction`).
4. **Prompt Delta**:
   - Minimal extension of root prompt adding the `## Hybrid Localization Strategy` section and updating Steps 3–4 to reinforce information-gain ordering.

---

## 3. Hybrid Routing Sequence & Decision Logic

The policy enforces a strict information-gain sequence:
```
Issue -> Cheap Exact Reconnaissance -> If Ambiguous -> Semantic Search -> If Symbol Found -> Inspect Source -> If Relations Unclear -> Graph Neighbors -> If Multiple Inspected Symbols Interact -> Subgraph -> Exact Source Inspection
```

### 3.1. Decision States
- `EXACT_STRONG`: Unambiguous exact match identified during reconnaissance; skip semantic retrieval and inspect source directly.
- `EXACT_AMBIGUOUS`: Exact search returned 0 matches, weak candidates, or conflicting subsystems; semantic retrieval justified.
- `SEMANTIC_NEEDED`: Issue terminology diverges from codebase symbols; semantic retrieval justified.
- `PROMISING_SYMBOL_FOUND`: Candidate symbol established; inspect source code before relational expansion.
- `RELATIONSHIP_NEEDED`: Promising symbol inspected in source, but surrounding callers/callees/definitions remain unresolved; 1-hop graph neighbors justified.
- `MULTI_SYMBOL_INTERACTION`: $\ge 2$ candidate symbols have been inspected and their joint interaction is central to the defect; induced subgraph retrieval justified.
- `SOURCE_SUFFICIENT`: Direct source code explains the defect; cease all retrieval immediately.
- `RETRIEVAL_BUDGET_EXHAUSTED`: Call budget, repeat limit, or search bounds reached; terminate retrieval.
- `NON_LOCALIZATION_PHASE`: Phase is edit, verify, or review; retrieval is disabled.

---

## 4. Policy Composition & TaskState Hygiene

1. **Composition without Bypassing**:
   - The hybrid controller evaluates global reconnaissance context and selects an action.
   - The corresponding specialized policy (`RetrievalPolicyV1`, `NeighborPolicyV1`, or `SubgraphPolicyV1`) validates that all local preconditions and constraints are satisfied.
   - Specialized policies execute their standard `integrate_results(...)` logic.
2. **TaskState Invariance**:
   - Reuses existing `TaskState` without schema modifications.
   - Retains collection size limit (`MAX_COLLECTION_SIZE = 50`).
   - Zero raw graph structures, full response payloads, or embedding vectors are stored in `TaskState`.
3. **Provenance & Auditing**:
   - Decisions are logged in lightweight `HybridDecisionRecord` instances containing timestamps, counts, state, action, and reasoning.

---

## 5. Tool Budget & Anti-Loop Safeguards

- `MAX_SEMANTIC_CALLS = 2`
- `MAX_NEIGHBOR_CALLS = 3`
- `MAX_SUBGRAPH_CALLS = 2`
- `MAX_TOTAL_RETRIEVAL_CALLS = 6`
- `MAX_CONSECUTIVE_REPEATS = 1` (blocks immediate redundant retrieval calls)
- Safe fallback to `STOP_RETRIEVAL` on any invalid or unexpected state.

---

## 6. Verification & Hashes

### 6.1. Submission Validator Result
```
=== Validating Submission Directory: experiments\candidates\E6 ===
Total Files Inspected: 3
Total YAML Files:      1
Total Unpacked Size:   6,944 bytes (0.01 MB)
Discovered Models:     ['gemma-4-31b-it-qat-w4a16-ct']

RESULT: PASSED (Schema, single-model rule, and limits verified)
```

### 6.2. SHA-256 Hashes
- **E6 `agent.yaml`**: `c2dec89c9df91bc9c0324ab43c379f7ef9fc6a79ae35af3bdd09e13e0d093724`
- **E6 `root.md`**: `fe9805fc39ef2e4861aa4ea9b0956985080012acef70397b3f485f083733278e`
- **Parent E5 `root.md`**: `d4128a6dc3d016422370cb6354a355971408463399196dcaf97e7ce04ec83756`

---

## 7. Anti-Fabrication & Empirical Limitation Disclosures

In strict adherence to the IMPULSE Constitution (`AGENTS.md`):
1. **No Live Gemma Inference**: Candidate E6 has not been evaluated against live `gemma-4-31b-it-qat-w4a16-ct` inference (unavailable on local host).
2. **No Real Benchmark Execution**: The full competition benchmark evaluation has not been executed locally.
3. **Zero Fabricated Scores**: `pass_rate: null`, `fail_rate: null`, `runtime: null`, `tool_count: null`.
4. **No Performance Claims**: There is no claim that hybrid localization improves task-solving pass rate over E5 on actual SWE-bench tasks until empirical runs on official infrastructure demonstrate it.
5. **No Stage 16+ Features**: Testing skill, repository triage, failure classifiers, no-progress detectors, recovery paths, and sub-agents are strictly deferred to subsequent stages.
