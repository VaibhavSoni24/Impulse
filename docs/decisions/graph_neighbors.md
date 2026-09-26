# Architectural Decision Record: Graph Neighbors (get_code_neighbors) — IMPULSE

**Status:** Accepted  
**Date:** 2026-09-26  
**Decision Makers:** IMPULSE Architecture Team  
**Consulted Documents:**
- [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) (Section 15, Stage 13)
- [HARNESS_README.md](file:///e:/Projects/Impulse/data/competition/HARNESS_README.md) (Sections 5.2, 6.3)
- [tool_contracts.md](file:///e:/Projects/Impulse/docs/decisions/tool_contracts.md) (Section 3.7)
- [semantic_retrieval.md](file:///e:/Projects/Impulse/docs/decisions/semantic_retrieval.md)

---

## 1. Context & Problem Statement

Candidate E3 introduced semantic retrieval (`search_similar_code`), enabling localization of candidate symbols even when problem descriptions use terminology that diverges from codebase identifiers. However, once a suspect symbol (class, function, or module) is located, understanding how that symbol interacts with callers, callees, definitions, and dependencies often requires manually tracing imports and cross-file usages.

In large codebases, doing this purely through repeated grep commands consumes tool budget and risks missing indirect callers or interface implementations.

To address this, the competition platform provides `get_code_neighbors` as part of its pre-computed AST/dependency graph tools. Candidate E4 introduces this capability:
$$\text{E4} = \text{E3} + \text{graph-neighbor retrieval (\texttt{get\_code\_neighbors})}$$

---

## 2. Tool Contract: `get_code_neighbors`

From authoritative inspection of `HARNESS_README.md` (Section 6.3) and `swegemma.tools.graph`:

### 2.1. Signature & Parameters
```python
get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str
```
- **`node`** (`str`, required): Symbol identifier (e.g., `"FastAPI.get"`, `"requests.adapters.HTTPAdapter"`).
  - *Symbol Resolution*: The harness implements a 4-tier resolver: exact match $\to$ `.` or `/` suffix match $\to$ case-insensitive match $\to$ substring match.
- **`edge_type`** (`str | None`, optional, default `None`): Optional edge filter (e.g., `"CALLS"`, `"DEFINED_IN"`, `"IMPORTS"`).
  - *Directionality*: When `edge_type` is omitted or specified, the underlying NetworkX graph queries incoming and outgoing adjacent edges connected to the node.
- **`max_neighbors`** (`int`, optional, default `50`): Maximum neighbors to return from the graph.
- **Budget Gating**: Annotated with `@budget_gated(count_tool_call=True)`. Each invocation debits the `tool_calls` budget by **1**.

### 2.2. Return Schema
Returns a serialized JSON string:
```json
{
  "status": "ok",
  "node": "fastapi.applications.FastAPI",
  "neighbors": [
    "fastapi.routing.APIRoute",
    "fastapi.datastructures.Default"
  ],
  "count": 2
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

## 3. Neighbor Invocation Policy (Stage 13)

Graph traversal can rapidly consume both tool call budget and context tokens if invoked indiscriminately. Candidate E4 enforces a strict, disciplined policy:

### 3.1. Prerequisite Sequence
Graph neighbors must follow the sequential information-gain flow:
```text
Issue
  ↓
Cheap exact reconnaissance
  ↓
Semantic search when E3 policy requires it
  ↓
Identify promising candidate symbol
  ↓
Inspect symbol/source context
  ↓
get_code_neighbors(node, edge_type=None, max_neighbors=50)
  ↓
Filter & select relevant neighbors
  ↓
Read exact source (read_file)
```

### 3.2. Trigger Conditions
Invoke `get_code_neighbors` **only** when all of the following hold:
1. **Identified Promising Symbol**: A suspect symbol or function has already been located via exact search or semantic retrieval.
2. **Relational Ambiguity**: The bug mechanism depends on understanding callers, callees, definitions, or imports connected to the candidate.
3. **Direct Source Insufficient**: Direct source reading of the candidate file leaves cross-module relationships unresolved.

### 3.3. Prohibited Invocations
The policy **prohibits**:
1. Invoking `get_code_neighbors` before identifying a suspect symbol.
2. Automatically expanding every candidate returned by `search_similar_code`.
3. Recursive or chained expansion (expanding neighbors of neighbors automatically).
4. Consecutive neighbor calls without intervening source inspection.
5. Invoking graph neighbors during editing or test verification phases.

---

## 4. Neighbor Selection & TaskState Integration

Per Stage 11 and Stage 12 standards, returned neighbor data must not pollute `TaskState` with raw unbounded payloads:

1. **Relevance Selection**:
   - The policy filters returned neighbor strings, retaining at most **5** directly relevant neighbor symbols (`MAX_RETAINED_NEIGHBORS = 5`).
2. **TaskState Ingestion**:
   - Retained neighbors are recorded in `TaskState.candidates`:
     - `path`: Neighbor node identifier or derived module path.
     - `symbol`: Neighbor node identifier.
     - `line_number`: `None` (resolved via `read_file`).
     - `rationale`: `"Graph neighbor of '<source_node>' (edge_type: '<edge_type>')"`
   - Provenance is recorded in `TaskState.evidence`:
     - `observation`: `"Graph relation discovered: '<source_node>' -> '<neighbor_node>'"`
     - `source_command_or_file`: `"get_code_neighbors(node='<source_node>')"`
3. **Source Reading Delegation**:
   - Graph neighbors provide node names only; actual code inspection is performed using `read_file` on targeted line ranges.

---

## 5. Execution Boundary & Anti-Fabrication Notice

1. **Local Workstation Status**:
   - Graph files (`data/graphs/<repo>.json`) are not present in the local repository; they exist only inside the official competition Docker scoring environment.
   - Remote vLLM inference with `gemma-4-31b-it-qat-w4a16-ct` is not available on this workstation.
2. **Structural Validation Only**:
   - E4 is validated structurally: submission schema, parameter parity with E3, tool registration, policy enforcement, and TaskState integration tests.
   - No synthetic graphs, fake neighbor lists, or benchmark pass rates are asserted (`pass_rate: null`).

---

## 6. Experimental Boundary (Stage 14 Invariance)

Candidate E4 implements **Stage 13 only**. It does NOT implement:
- `get_code_subgraph` (Stage 14);
- Multi-hop recursive graph expansion;
- Hybrid retrieval controller (Stage 15);
- Sub-agents, skills, context compaction, or LoRA.
