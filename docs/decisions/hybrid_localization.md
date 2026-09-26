# Architectural Decision Record: Hybrid Localization Policy — IMPULSE

**Status:** Accepted  
**Date:** 2026-09-26  
**Decision Makers:** IMPULSE Architecture Team  
**Consulted Documents:**
- [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) (Section 17, Stage 15)
- [HARNESS_README.md](file:///e:/Projects/Impulse/data/competition/HARNESS_README.md) (Sections 5.2, 6.3)
- [tool_contracts.md](file:///e:/Projects/Impulse/docs/decisions/tool_contracts.md)
- [semantic_retrieval.md](file:///e:/Projects/Impulse/docs/decisions/semantic_retrieval.md)
- [graph_neighbors.md](file:///e:/Projects/Impulse/docs/decisions/graph_neighbors.md)
- [subgraph_retrieval.md](file:///e:/Projects/Impulse/docs/decisions/subgraph_retrieval.md)

---

## 1. Context & Problem Statement

Prior candidates introduced isolated retrieval capabilities:
- **E3** introduced semantic search (`search_similar_code`) to handle vocabulary mismatch and ambiguous search terms.
- **E4** introduced 1-hop relational exploration (`get_code_neighbors`) to inspect callers, callees, and definitions around an established symbol.
- **E5** introduced induced subgraph retrieval (`get_code_subgraph`) to analyze multi-symbol interactions.

However, having all three retrieval tools available introduces the risk of indiscriminate or mechanical retrieval chaining:
$$\text{Issue} \longrightarrow \texttt{search\_similar\_code} \longrightarrow \texttt{get\_code\_neighbors} \longrightarrow \texttt{get\_code\_subgraph}$$

Blindly executing this chain on every task causes:
1. **Severe Tool Budget Depletion**: The competition platform enforces strict budget gating (`@budget_gated(count_tool_call=True)`). Each retrieval tool invocation consumes a tool call unit.
2. **Context Window Pollution**: Redundant graph queries introduce excess token overhead, crowding out targeted source code and test diagnostics.
3. **Retrieval Loops**: Without explicit state tracking and termination bounds, agents may oscillate between semantic and graph queries without converging on actual source code.

Candidate E6 solves this by introducing the **Hybrid Localization Policy V1**:
$$\text{E6} = \text{E5} + \text{Hybrid Localization Policy V1}$$

---

## 2. Information-Gain Architecture

The hybrid localization policy implements an **information-gain hierarchy**, prioritizing cheaper, higher-precision evidence before escalating to higher-cost semantic and graph queries:

```
                  ┌───────────────────────────────┐
                  │          Issue Text           │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │    Phase A: Cheap Exact       │
                  │ Reconnaissance (grep, files)  │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────┴───────────────┐
       [Exact Strong Match]               [Ambiguous / Weak]
                  │                               │
                  │                               ▼
                  │               ┌───────────────────────────────┐
                  │               │   Phase B: Semantic Search    │
                  │               │     (search_similar_code)     │
                  │               └───────────────┬───────────────┘
                  │                               │
                  ▼                               ▼
       ┌──────────────────────────────────────────────────────────┐
       │             Candidate Symbol Established                 │
       │           (inspect direct source via read_file)          │
       └──────────────────────────┬───────────────────────────────┘
                                  │
                  ┌───────────────┴───────────────┐
        [Source Sufficient]             [Relations Unclear]
                  │                               │
                  │                               ▼
                  │               ┌───────────────────────────────┐
                  │               │    Phase C: Graph Neighbors   │
                  │               │     (get_code_neighbors)      │
                  │               └───────────────┬───────────────┘
                  │                               │
                  │               ┌───────────────┴───────────────┐
                  │      [Single Node Context]       [Multi-Symbol Interaction]
                  │               │                               │
                  │               │                               ▼
                  │               │               ┌───────────────────────────────┐
                  │               │               │      Phase D: Subgraph        │
                  │               │               │      (get_code_subgraph)      │
                  │               │               └───────────────┬───────────────┘
                  │               │                               │
                  └───────────────┼───────────────────────────────┘
                                  ▼
                  ┌───────────────────────────────┐
                  │ Phase E: Read Exact Source    │
                  │ (read_file / stop retrieval)  │
                  └───────────────────────────────┘
```

The system does **NOT** invoke all retrieval tools automatically. Each transition is gated by explicit evidence conditions.

---

## 3. Decision Model & State Transitions

The controller is deterministic, auditable, and bounded. It evaluates the current reconnaissance context and outputs an explicit decision record.

### 3.1. Decision States (`DecisionState`)
- **`EXACT_STRONG`**: Unambiguous exact match identified during reconnaissance. Skip semantic retrieval and inspect source directly.
- **`EXACT_AMBIGUOUS`**: Exact search returned zero matches, weak candidates, or multiple conflicting subsystems. Semantic retrieval is justified.
- **`SEMANTIC_NEEDED`**: Issue terminology diverges from codebase symbols. Semantic retrieval is justified.
- **`PROMISING_SYMBOL_FOUND`**: A candidate symbol has been identified (via exact or semantic search). Inspect source code before expanding relations.
- **`RELATIONSHIP_NEEDED`**: Promising symbol inspected in source, but surrounding callers, callees, or definitions remain unresolved. 1-hop graph neighbors justified.
- **`MULTI_SYMBOL_INTERACTION`**: Multiple candidate symbols ($\ge 2$) have been inspected, and their mutual interaction is central to the defect. Induced subgraph retrieval justified.
- **`SOURCE_SUFFICIENT`**: Direct source code explains the defect. Stop all retrieval operations.
- **`RETRIEVAL_BUDGET_EXHAUSTED`**: Tool budget, repeated action limit, or search bounds reached. Stop retrieval to avoid infinite loops.
- **`NON_LOCALIZATION_PHASE`**: Current phase is editing, verification, or review. Retrieval is disabled.

### 3.2. Localization Actions (`LocalizationAction`)
- **`EXACT_SEARCH`**: Execute cheap exact reconnaissance (text matching or directory structure inspection).
- **`SEMANTIC_SEARCH`**: Invoke `search_similar_code(query, k)`.
- **`INSPECT_SOURCE`**: Read targeted source files using `read_file`.
- **`GRAPH_NEIGHBORS`**: Invoke `get_code_neighbors(node, edge_type, max_neighbors)`.
- **`SUBGRAPH`**: Invoke `get_code_subgraph(nodes)`.
- **`STOP_RETRIEVAL`**: Conclude retrieval operations and transition to hypothesis formulation and editing.

### 3.3. State Transition Matrix
| Current Condition | Next State | Next Action | Rationale |
| :--- | :--- | :--- | :--- |
| Phase $\ne$ `"localization"` | `NON_LOCALIZATION_PHASE` | `STOP_RETRIEVAL` | Retrieval tools prohibited during edit/verify/review. |
| Direct source sufficient | `SOURCE_SUFFICIENT` | `STOP_RETRIEVAL` | Defect localized; avoid redundant tool calls. |
| Budget / repeat limits reached | `RETRIEVAL_BUDGET_EXHAUSTED` | `STOP_RETRIEVAL` | Prevent unbounded retrieval loops. |
| Exact search unambiguous ($\approx 1$ strong match) | `EXACT_STRONG` | `INSPECT_SOURCE` | Exact match suffices; semantic search would be redundant. |
| Exact search 0 matches or ambiguous | `EXACT_AMBIGUOUS` | `SEMANTIC_SEARCH` | Disambiguation needed via embedding similarity. |
| Candidate symbol found, uninspected | `PROMISING_SYMBOL_FOUND` | `INSPECT_SOURCE` | Always read source before expanding graph. |
| Symbol inspected, relations unclear | `RELATIONSHIP_NEEDED` | `GRAPH_NEIGHBORS` | Explore 1-hop context of established candidate. |
| $\ge 2$ symbols inspected, joint interaction | `MULTI_SYMBOL_INTERACTION` | `SUBGRAPH` | Induced subgraph clarifies inter-symbol coupling. |
| Single neighbor sufficient | `PROMISING_SYMBOL_FOUND` | `INSPECT_SOURCE` | Subgraph skipped when 1-hop neighbor suffices. |

---

## 4. Policy Composition Architecture

The hybrid controller does **not** duplicate or replace the specialized policies from E3, E4, and E5. It **composes** them:

```
HybridLocalizationPolicy
    ├── RetrievalPolicyV1   (local.retrieval.controller)
    ├── NeighborPolicyV1    (local.graph.controller)
    └── SubgraphPolicyV1    (local.subgraph.controller)
```

### 4.1. Execution Flow
1. **Decision**: `HybridLocalizationPolicy.choose_next_localization_action(context)` evaluates the global state and proposes a candidate action.
2. **Specialized Validation**: The corresponding specialized policy validates that its local constraints are satisfied:
   - For `SEMANTIC_SEARCH`, `RetrievalPolicyV1.should_retrieve(...)` validates ambiguity and phase.
   - For `GRAPH_NEIGHBORS`, `NeighborPolicyV1.should_retrieve(...)` validates candidate promise and unexpanded status.
   - For `SUBGRAPH`, `SubgraphPolicyV1.should_retrieve(...)` validates that $\ge 2$ candidate symbols were inspected and interaction is multi-symbol.
3. **Execution & Integration**: When a retrieval operation occurs, its result is processed by the specialized policy's `integrate_results(...)`, which updates `TaskState` concisely.
4. **Audit & Tracking**: The hybrid controller records the decision and updates internal call counters, consecutive repeat counters, and convergence status.

---

## 5. Tool Budget & Anti-Loop Safeguards

To prevent infinite loops and budget exhaustion, the hybrid policy enforces strict upper bounds:
- **`MAX_SEMANTIC_CALLS` = 2**: A maximum of 2 semantic searches per issue. If two queries fail to localize the subsystem, further semantic search is unlikely to help.
- **`MAX_NEIGHBOR_CALLS` = 3**: A maximum of 3 graph neighbor expansions.
- **`MAX_SUBGRAPH_CALLS` = 2**: A maximum of 2 subgraph queries.
- **`MAX_TOTAL_RETRIEVAL_CALLS` = 6**: Total combined retrieval operations cannot exceed 6.
- **`MAX_CONSECUTIVE_REPEATS` = 1**: The controller blocks consecutive identical retrieval actions without intervening source inspection.
- **Fail-Safe Fallback**: Any unexpected, unknown, or invalid context transitions safely to `STOP_RETRIEVAL` rather than executing speculative tool calls.

---

## 6. TaskState Integration & Payload Hygiene

In accordance with [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) Section 13:
- **No Schema Changes**: Reuses existing `TaskState` without altering its fields or invariants.
- **No Raw Payload Dumps**: Raw graph responses, embeddings, adjacency lists, and multi-KB search payloads are never written to `TaskState`.
- **Bounded Collections**: All lists in `TaskState` retain their strict `MAX_COLLECTION_SIZE = 50` ceiling.
- **Provenance Logging**: Decisions are recorded in lightweight `HybridDecisionRecord` instances for offline auditing without consuming prompt tokens.

---

## 7. Local Workstation Limitations & Anti-Fabrication Notice

1. **Local Workstation Status**:
   - `data/graphs/<repo>.json` files and live vLLM inference for `gemma-4-31b-it-qat-w4a16-ct` are unavailable on this local development environment.
2. **Structural Validation Only**:
   - E6 is validated structurally: submission schema compliance, generation configuration invariance, policy gating, deterministic state transitions, and integration with `TaskState`.
   - **Zero fabricated numbers**: No benchmark scores, pass rates, latency metrics, or runtime claims are asserted (`pass_rate: null`).
   - No empirical winner among retrieval strategies is selected on this workstation.

---

## 8. Hard Stage 16 Boundary

Candidate E6 implements **Stage 15 only**. It does **NOT** implement:
- Stage 16 Testing Skill;
- Stage 17 Repository Triage Skill;
- Stage 18 Failure Classification;
- Stage 19 No-Progress Detector;
- Stage 20 Recovery Paths;
- Sub-agents (Scout, Debugger, Reviewer) or LoRA fine-tuning.
