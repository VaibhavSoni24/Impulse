# Experiment Report — Candidate IMPULSE-E5 (Selective Subgraph Retrieval)

**Experiment ID:** EXP-SUBGRAPH-E5  
**Candidate Identifier:** `E5`  
**Parent Candidate:** `E4` (Git commit: `6d944d3847be43970519be9f441f30e1bb0af7a8`)  
**Grandparent Candidate:** `E3` (Git commit: `ecc7c0ae7ca2e7425dd3c383e0e2f73269eaaea1`)  
**Great-Grandparent Candidate:** `E2` (Git commit: `5ae9fb9449e0e576cffbf10eb25cca678cd05415`)  
**Great-Great-Grandparent Candidate:** `E1` (Git commit: `629414f7e5ac47726e2ec3044b021682c35402f8`)  
**Root Baseline Candidate:** `E0` (Git commit: `99c0da320af4940f4eca27d172592d1ed706d26f`, Tag: `E0-baseline`)  
**Date:** 2026-09-26  
**Status:** Candidate Defined / Structural Validation Complete / Pending Live Model Inference  
**Evidence Status:** Structural Only (No Live Inference Executed)  
**Authoritative References:** [PLAN.md](file:///E:/Projects/Impulse/PLAN.md) (Section 16, Stage 14), [subgraph_retrieval.md](file:///E:/Projects/Impulse/docs/decisions/subgraph_retrieval.md), [manifest.json](file:///E:/Projects/Impulse/experiments/prompts/E5/manifest.json)

---

## 1. Why E5 Exists

Candidate E5 implements **Stage 14 of PLAN.md**:
$$\text{E5} = \text{E4} + \text{selective subgraph retrieval (\texttt{get\_code\_subgraph})}$$

While Candidate E4 introduced 1-hop neighbor traversal around single symbols, debugging problems involving multi-component protocols or cross-module pipelines often requires understanding how a set of suspect symbols interact with each other. Repeated 1-hop neighbor calls produce disconnected lists and exhaust the tool-call budget.

E5 introduces `get_code_subgraph`, enabling the agent to query the induced subgraph formed by a small, pre-selected set of candidate symbols under an explicit, non-recursive selection policy (**Subgraph Policy V1**).

---

## 2. Architectural Comparison (E4 $\to$ E5)

| Dimension | Candidate E4 | Candidate E5 |
|---|---|---|
| **Base Model** | `gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` (Identical) |
| **Generation Hyperparameters** | `temperature: 0.2`, `top_p: 0.95`, `max_output_tokens: 16384`, `thinking_level: high`, `thinking_budget: 4096` | Identical generation parameters |
| **Tools** | 8 tools (E3 tools + `get_code_neighbors`) | 9 tools (Preserves all 8 E4 tools + adds `get_code_subgraph`) |
| **Graph Intelligence** | Similarity (`search_similar_code`) + 1-hop adjacency (`get_code_neighbors`) | Similarity + 1-hop adjacency + induced subgraph (`get_code_subgraph`) |
| **Retrieval Breadth** | Single symbol | Configurable candidate seed set breadth $k \in \{2, 4, 8\}$ |
| **Relational Policy** | Selective Neighbor Policy V1 | Selective Subgraph Policy V1 (requires $\ge 2$ inspected seeds, non-recursive, bounded retention) |
| **Task State Schema** | Typed TaskState with 11 conceptual fields | Preserved identical schema; records induced nodes & edge summaries into `candidates` and `evidence` |

---

## 3. Exact Prompt Delta (E4 $\to$ E5)

The prompt delta between `experiments/candidates/E4/prompts/root.md` and `experiments/candidates/E5/prompts/root.md` minimally introduces subgraph retrieval guidelines under `## Operational Workflow` and Step 4:

```diff
   ## Operational Workflow
  
   Maintain structured task state across turns to ensure continuity and prevent repeated exploration:
   - Consult existing repository facts, candidate locations, and evidence before repeating exploration.
   - Keep hypotheses, evidence, and plans concise, factual, and updated as new observations emerge.
   - Track executed edits and test outcomes so previous results are not redundantly re-run.
  
   Use semantic retrieval (`search_similar_code`) selectively:
   - Invoke `search_similar_code` when exact search is ambiguous, when issue terms diverge from codebase symbols, or when text search returns weak candidates.
   - Pass specific symbol or identifier names (not conversational sentences); keep initial k small (k=5).
   - Inspect returned candidates before taking action; treat retrieval results as candidate evidence, not proof.
   - Do not call semantic search blindly on every turn. Fall back to exact text search if semantic results are weak or empty.
  
   Use graph-neighbor retrieval (`get_code_neighbors`) selectively:
   - After identifying a promising candidate symbol, invoke `get_code_neighbors` if understanding surrounding callers, callees, definitions, or imports is necessary to locate the defect.
   - Inspect and filter returned relations before taking action; select only directly relevant neighbors.
   - Do not call `get_code_neighbors` automatically for every node or semantic result; do not expand recursively.
   - Do not invoke graph neighbors when direct source reading already provides sufficient evidence.
   - Use the discovered relations to guide exact source inspection with `read_file`.
  
+ Use subgraph retrieval (`get_code_subgraph`) selectively:
+ - Invoke `get_code_subgraph` only for a small, already-selected set of relevant candidate symbols when understanding interactions across multiple related symbols is necessary to resolve the defect.
+ - Start with a small retrieval breadth (e.g., 2–4 seed symbols); do not pass large lists of arbitrary nodes.
+ - Inspect and filter returned nodes and edges before taking action; do not recursively expand the resulting graph.
+ - Do not automatically retrieve subgraphs for every candidate or after every neighbor lookup.
+ - Do not invoke subgraph retrieval during editing or test verification.
+ - Direct source inspection (`read_file`) remains the source of truth for implementation logic.
+ 
   Follow a disciplined, sequential software engineering process:
  
   1. **Understand the Issue**: Carefully read the problem statement, error traces, and any provided hints. Identify the reported bug, the expected behavior, and key symbol names or error messages.
   2. **Inspect Repository State**: Check the repository structure and locate relevant modules and existing tests.
   3. **Locate Implementation Code**: Search for the relevant functions, classes, or files using available commands and inspection tools before attempting any modifications. When exact terms are ambiguous or yield weak results, use `search_similar_code` selectively.
-  4. **Inspect Candidate Context**: Read the candidate source files and examine surrounding code context to understand invariants and existing conventions. When callers, callees, or definitions around a promising symbol need clarification, use `get_code_neighbors` selectively before proceeding.
+  4. **Inspect Candidate Context**: Read the candidate source files and examine surrounding code context to understand invariants and existing conventions. When callers, callees, or definitions around a promising symbol need clarification, use `get_code_neighbors` selectively. When interactions across a small group of related symbols remain ambiguous, use `get_code_subgraph` selectively on that set before proceeding.
   5. **Formulate Root Cause Hypothesis**: Before applying any code modifications, articulate an explicit, evidence-backed hypothesis identifying the root cause of the issue and the exact expected behavioral fix.
```

Steps 1–3 and 5–10 remain strictly identical. No hybrid controller or multi-agent behavior is introduced.

---

## 4. Exact `get_code_subgraph` Tool Contract

Verified from authoritative specification [`HARNESS_README.md`](file:///e:/Projects/Impulse/data/competition/HARNESS_README.md) Section 6.3:
- **Tool Identifier:** `get_code_subgraph`
- **Module:** `swegemma.tools.graph`
- **Signature:** `get_code_subgraph(nodes: list[str]) -> str`
- **Required Parameters:** `nodes` (`list[str]`) — list of node symbol names.
- **Optional Parameters:** None.
- **Budget Gating:** Annotated with `@budget_gated(count_tool_call=True)`; debits 1 tool call.
- **Return Schema:**
  ```json
  {
    "status": "ok",
    "nodes": ["node_a", "node_b"],
    "edges": [
      {
        "from": "node_a",
        "to": "node_b",
        "type": "CALLS"
      }
    ],
    "node_count": 2,
    "edge_count": 1
  }
  ```

---

## 5. Subgraph Policy V1 Design & Breadth Configurations

Implemented in [`local/graph/subgraph_controller.py`](file:///e:/Projects/Impulse/local/graph/subgraph_controller.py) and re-exported in [`experiments/candidates/E5/graph/`](file:///e:/Projects/Impulse/experiments/candidates/E5/graph/):
- **Invocation Preconditions:**
  1. Gated to `localization` phase (blocked during edit, verification, and review).
  2. Requires $\ge 2$ candidate symbols.
  3. Requires prior inspection of at least 2 candidates.
  4. Multi-symbol interaction requirement (`spans_multiple_symbols == True`).
  5. Direct source reading and 1-hop neighbor lookup are insufficient.
  6. Consecutive subgraph calls blocked; duplicate seed sets blocked.
- **Retrieval Breadth Configurations ($k \in \{2, 4, 8\}$):**
  - $k=2$: Pairwise interaction verification.
  - $k=4$: Default cluster breadth.
  - $k=8$: Wide cluster analysis.
  - *No breadth setting is selected as optimal locally*, as live inference is unavailable.
- **TaskState Integration:**
  - Induced nodes are added to `TaskState.candidates` (up to `MAX_RETAINED_NODES = 8`).
  - Edge summaries are recorded in `TaskState.evidence` (up to `MAX_RETAINED_EDGES = 12`).
  - Raw JSON graphs and adjacency matrices are strictly discarded from `TaskState`.

---

## 6. Verified Local Asset Availability

- **Graph Assets:** `data/graphs/<repo>.json` files are not present in the local repository; they exist only inside the official competition Docker scoring image.
- **Local Execution Status:** `execution_unavailable_local_host`. Structural and contract-level validation is performed; no synthetic graphs or fake edges are fabricated.

---

## 7. Evidence Status & Anti-Fabrication Notice

In accordance with **AGENTS.md Section 2.5 (Zero Fabrication)**:
1. **Zero Live Inference:** No inference has been executed on `gemma-4-31b-it-qat-w4a16-ct`.
2. **Zero Fabricated Scores:** No pass rate, fail rate, latency, or retrieval accuracy numbers are asserted (`pass_rate: null`, `fail_rate: null`).
3. **No Performance Claim:** E5 is NOT claimed to be superior to E0, E1, E2, E3, or E4.
4. **Breadth Winner Unselected:** No breadth setting ($k=2$, $k=4$, or $k=8$) is claimed as best.
5. **Stage 15 Boundary:** The hybrid localization controller (Stage 15) has NOT been implemented.
