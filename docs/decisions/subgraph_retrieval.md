# Architectural Decision Record: Selective Subgraph Retrieval (get_code_subgraph) — IMPULSE

**Status:** Accepted  
**Date:** 2026-09-26  
**Decision Makers:** IMPULSE Architecture Team  
**Consulted Documents:**
- [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) (Section 16, Stage 14)
- [HARNESS_README.md](file:///e:/Projects/Impulse/data/competition/HARNESS_README.md) (Sections 5.2, 6.3)
- [tool_contracts.md](file:///e:/Projects/Impulse/docs/decisions/tool_contracts.md) (Section 3.9)
- [graph_neighbors.md](file:///e:/Projects/Impulse/docs/decisions/graph_neighbors.md)
- [semantic_retrieval.md](file:///e:/Projects/Impulse/docs/decisions/semantic_retrieval.md)

---

## 1. Context & Problem Statement

Candidate E4 introduced 1-hop relational exploration via `get_code_neighbors(node, edge_type, max_neighbors)`. While effective for inspecting immediate callers or callees of a single suspect symbol, issues involving multi-module protocols, client-server abstractions, or inter-class data pipelines often require understanding how a *set* of known candidate symbols interact with one another.

Querying `get_code_neighbors` repeatedly for each symbol produces disconnected adjacency lists and consumes tool call budget without clarifying the direct connections between the candidates.

To address this, the competition platform exposes `get_code_subgraph`, which extracts the induced subgraph formed by a set of nodes. Candidate E5 integrates this tool:
$$\text{E5} = \text{E4} + \text{selective subgraph retrieval (\texttt{get\_code\_subgraph})}$$

---

## 2. Authoritative Tool Contract: `get_code_subgraph`

From authoritative inspection of `HARNESS_README.md` (Section 6.3) and `swegemma.tools.graph`:

### 2.1. Signature & Parameters
```python
get_code_subgraph(nodes: list[str]) -> str
```
- **`nodes`** (`list[str]`, required): List of node symbol names (e.g., `["requests.models.Request", "requests.adapters.HTTPAdapter"]`).
- **Optional Parameters:** **None**. The official tool contract accepts only `nodes: list[str]`. There are no additional parameters for hop depth, direction, or edge filtering on this tool.
- **Budget Gating:** Annotated with `@budget_gated(count_tool_call=True)`. Each invocation debits the `tool_calls` budget by **1**.

### 2.2. Return Schema
Returns a serialized JSON string:
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
Or on error:
```json
{
  "status": "error",
  "error_type": "<ErrorClass>",
  "error_message": "<Description>",
  "details": { ... }
}
```

---

## 3. Subgraph Policy V1 Design

Induced subgraph retrieval must be strictly bounded to prevent context explosion and avoid wasteful tool calls.

### 3.1. Invocation Prerequisites
`get_code_subgraph` may be invoked **only** when all of the following criteria are satisfied:
1. **Localization Phase**: The agent is in the `localization` phase (never during editing, verification, or review).
2. **Pre-Selected Relevant Symbol Set**: A small set of candidate symbols ($\ge 2$) has already been identified via reconnaissance, semantic search, or neighbor lookups.
3. **Prior Candidate Inspection**: At least two of the candidate symbols have already been inspected to verify relevance.
4. **Multi-Symbol Interaction**: The defect mechanism spans interactions between multiple symbols rather than an isolated function.
5. **Direct Source Insufficient**: Reading direct source or single-node 1-hop neighbors does not adequately explain the inter-component contract.

### 3.2. Prohibited Behaviors
The policy **strictly prohibits**:
1. Invoking `get_code_subgraph` before selecting a candidate symbol set.
2. Invoking `get_code_subgraph` on a single symbol (1-hop `get_code_neighbors` should be used instead).
3. Automatically running subgraph retrieval after every candidate search.
4. Consecutive subgraph calls without intermediate source inspection.
5. Multi-stage recursive graph crawling (expanding nodes returned from a previous subgraph).
6. Invoking subgraph retrieval during edit, test verification, or review phases.

---

## 4. Retrieval Breadth Experimentation ($k \in \{2, 4, 8\}$)

Per [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) Stage 14, retrieval breadth is systematically bounded:
- In the `get_code_subgraph` contract, $k$ corresponds to the **seed candidate set size** ($|V_{\text{seed}}| = k$).
- The policy supports three explicit candidate breadth configurations:
  - **$k = 2$**: Minimal pair-wise interaction analysis (tightest context, lowest token footprint).
  - **$k = 4$**: Small subsystem cluster (balances cross-file coverage with context economy).
  - **$k = 8$**: Broader module interaction analysis (higher context usage, wider coverage).
- Because live Gemma inference is not present on this workstation, **no breadth configuration is declared superior locally**. Bounded parameter support is structurally established for future remote evaluation.

---

## 5. TaskState Integration & Payload Hygiene

To protect the 32,768-token context window and maintain clean task state:
1. **Candidate Logging**: Retained induced nodes (up to `MAX_RETAINED_NODES = 8`) are appended to `TaskState.candidates`:
   - `path`: Node identifier or derived module path.
   - `symbol`: Node identifier.
   - `rationale`: `"Induced subgraph node connected via <N> relation(s)"`.
2. **Evidence Logging**: A concise edge summary (up to `MAX_RETAINED_EDGES = 12`) is recorded in `TaskState.evidence`:
   - `observation`: `"Subgraph relations identified: <node_a> -[CALLS]-> <node_b>"`.
   - `source_command_or_file`: `"get_code_subgraph(nodes=[...])"`.
3. **Payload Sanitization**: Raw adjacency matrices, massive JSON node lists, and code blobs are strictly excluded from `TaskState`. Source logic must be examined via targeted `read_file` calls.

---

## 6. Execution Boundary & Anti-Fabrication Notice

1. **Local Workstation Status**:
   - `data/graphs/<repo>.json` files exist only inside the official competition Docker scoring image.
   - Remote vLLM inference with `gemma-4-31b-it-qat-w4a16-ct` is unavailable on this workstation.
2. **Structural Validation Only**:
   - E5 is validated structurally (submission schema, tool parity, generation configuration invariance, policy gating, and deterministic TaskState bounds).
   - Zero synthetic graph data, mock responses, or benchmark pass rates are fabricated (`pass_rate: null`).

---

## 7. Hard Stage 15 Boundary

Candidate E5 implements **Stage 14 only**. It does NOT implement:
- Stage 15 Hybrid Localization Controller;
- Automated multi-tool routing;
- Sub-agents, skills, recovery loops, or LoRA.
