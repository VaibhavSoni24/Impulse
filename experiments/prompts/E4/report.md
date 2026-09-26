# Experiment Report — Candidate IMPULSE-E4 (Graph Neighbors)

**Experiment ID:** EXP-GRAPH-E4  
**Candidate Identifier:** `E4`  
**Parent Candidate:** `E3` (Git commit: `ecc7c0ae7ca2e7425dd3c383e0e2f73269eaaea1`)  
**Grandparent Candidate:** `E2` (Git commit: `5ae9fb9449e0e576cffbf10eb25cca678cd05415`)  
**Great-Grandparent Candidate:** `E1` (Git commit: `629414f7e5ac47726e2ec3044b021682c35402f8`)  
**Root Baseline Candidate:** `E0` (Git commit: `99c0da320af4940f4eca27d172592d1ed706d26f`, Tag: `E0-baseline`)  
**Date:** 2026-09-26  
**Status:** Candidate Defined / Structural Validation Complete / Pending Live Model Inference  
**Evidence Status:** Structural Only (No Live Inference Executed)  
**Authoritative References:** [PLAN.md](file:///E:/Projects/Impulse/PLAN.md) (Section 15, Stage 13), [graph_neighbors.md](file:///E:/Projects/Impulse/docs/decisions/graph_neighbors.md), [manifest.json](file:///E:/Projects/Impulse/experiments/prompts/E4/manifest.json)

---

## 1. Why E4 Exists

Candidate E4 implements **Stage 13 of PLAN.md**:
$$\text{E4} = \text{E3} + \text{graph-neighbor retrieval (\texttt{get\_code\_neighbors})}$$

While Candidate E3 introduced semantic retrieval (`search_similar_code`) to locate suspect symbols from conceptual problem descriptions, complex bug mechanisms often span caller-callee chains, interface implementations, and cross-module dependencies. Investigating these interactions purely via regex or filesystem searches consumes precious tool calls and risks omitting indirect call sites.

E4 integrates `get_code_neighbors`, allowing the agent to query the pre-computed AST call and dependency graph for relationships connected to an established candidate symbol, under an explicit, non-recursive selection policy (**Neighbor Policy V1**).

---

## 2. Architectural Comparison (E3 $\to$ E4)

| Dimension | Candidate E3 | Candidate E4 |
|---|---|---|
| **Architecture Base** | Baseline + structured `TaskState` + semantic retrieval | Identical base + structured `TaskState` + semantic retrieval + graph neighbors |
| **Model** | `gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` (Identical) |
| **Tools** | 7 tools (`run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `search_similar_code`) | 8 tools (Preserves all 7 E3 tools + adds `get_code_neighbors`) |
| **Generation Hyperparameters** | `temperature: 0.2`, `top_p: 0.95`, `max_output_tokens: 16384`, `thinking_level: high`, `thinking_budget: 4096` | Identical generation parameters |
| **Graph Intelligence** | Embedding cosine similarity (`search_similar_code`) | Embedding cosine similarity + in-memory NetworkX adjacency traversal (`get_code_neighbors`) |
| **Relational Policy** | N/A | Selective Neighbor Policy V1 (requires promising symbol; non-recursive; max 5 retained) |
| **Task State Continuity** | Preserves 11 fields, concise semantic candidate logging | Preserves identical schema; records relational edges into `candidates` and `evidence` |

---

## 3. Exact Prompt Delta (E3 $\to$ E4)

The prompt delta between `experiments/candidates/E3/prompts/root.md` and `experiments/candidates/E4/prompts/root.md` minimally introduces graph neighbor guidelines under `## Operational Workflow` and Step 4:

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
  
+ Use graph-neighbor retrieval (`get_code_neighbors`) selectively:
+ - After identifying a promising candidate symbol, invoke `get_code_neighbors` if understanding surrounding callers, callees, definitions, or imports is necessary to locate the defect.
+ - Inspect and filter returned relations before taking action; select only directly relevant neighbors.
+ - Do not call `get_code_neighbors` automatically for every node or semantic result; do not expand recursively.
+ - Do not invoke graph neighbors when direct source reading already provides sufficient evidence.
+ - Use the discovered relations to guide exact source inspection with `read_file`.
+ 
   Follow a disciplined, sequential software engineering process:
  
   1. **Understand the Issue**: Carefully read the problem statement, error traces, and any provided hints. Identify the reported bug, the expected behavior, and key symbol names or error messages.
   2. **Inspect Repository State**: Check the repository structure and locate relevant modules and existing tests.
   3. **Locate Implementation Code**: Search for the relevant functions, classes, or files using available commands and inspection tools before attempting any modifications. When exact terms are ambiguous or yield weak results, use `search_similar_code` selectively.
-  4. **Inspect Candidate Context**: Read the candidate source files and examine surrounding code context to understand invariants and existing conventions.
+  4. **Inspect Candidate Context**: Read the candidate source files and examine surrounding code context to understand invariants and existing conventions. When callers, callees, or definitions around a promising symbol need clarification, use `get_code_neighbors` selectively before proceeding.
   5. **Formulate Root Cause Hypothesis**: Before applying any code modifications, articulate an explicit, evidence-backed hypothesis identifying the root cause of the issue and the exact expected behavioral fix.
```

Steps 1–3 and 5–10 remain strictly identical. No subgraph instructions are introduced.

---

## 4. Exact `get_code_neighbors` Tool Contract

Verified from authoritative specification [`HARNESS_README.md`](file:///e:/Projects/Impulse/data/competition/HARNESS_README.md) Section 6.3:
- **Tool Identifier:** `get_code_neighbors`
- **Module:** `swegemma.tools.graph`
- **Signature:** `get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str`
- **Budget Gating:** Debits 1 tool call from the agent's tool budget.
- **Node Identifier Resolution:** 4-tier symbol resolver: exact $\to$ suffix (`.` or `/`) $\to$ case-insensitive $\to$ substring.
- **Edge Filtering:** Optional `edge_type` parameter (`"CALLS"`, `"DEFINED_IN"`, `"IMPORTS"`).
- **Return Format:** Standard JSON response:
  ```json
  {"status": "ok", "node": "fastapi.applications.FastAPI", "neighbors": ["..."], "count": 18}
  ```

---

## 5. Neighbor Policy V1 & TaskState Integration

Implemented in [`local/graph/controller.py`](file:///e:/Projects/Impulse/local/graph/controller.py) and re-exported in [`experiments/candidates/E4/graph/`](file:///e:/Projects/Impulse/experiments/candidates/E4/graph/):
- **Gating Invariants:**
  - Requires `target_symbol` to be established as a promising candidate.
  - Requires that direct source inspection is insufficient to explain the bug mechanism.
  - Blocks consecutive neighbor calls without intermediate source inspection.
  - Blocks re-expansion of previously expanded nodes (`expanded_nodes` tracking).
  - Disabled outside `localization` phase.
- **TaskState Integration:**
  - Retains at most **5** relevant neighbors (`MAX_RETAINED_NEIGHBORS = 5`).
  - Records retained neighbors into `TaskState.candidates` with symbol name and relationship rationale.
  - Appends audit trail to `TaskState.evidence`.
  - Discards raw graph structures or code dumps.
- **Why Unrestricted Graph Expansion Is Avoided:**
  Unrestricted graph expansion causes rapid exponential context growth ($O(d^k)$ tokens), exhausts the 50-tool-call budget, and floods reasoning with tangential caller/callee paths.

---

## 6. Verified Local Asset Availability

- **Graph Assets:** `data/graphs/<repo>.json` files are not present in the local repository; they exist only inside the competition scoring image.
- **Local Execution Status:** `execution_unavailable_local_host`. Structural and contract-level validation is performed; no fake graph responses or synthetic edges are fabricated.

---

## 7. Evidence Status & Anti-Fabrication Notice

In accordance with **AGENTS.md Section 2.5 (Zero Fabrication)**:
1. **Zero Live Inference:** No inference has been executed on `gemma-4-31b-it-qat-w4a16-ct`.
2. **Zero Fabricated Scores:** No pass rate, fail rate, latency, or retrieval accuracy numbers are asserted (`pass_rate: null`, `fail_rate: null`).
3. **No Performance Claim:** E4 is NOT claimed to be superior to E0, E1, E2, or E3.
4. **Stage 14 Boundary:** `get_code_subgraph` and selective subgraph retrieval have NOT been implemented.
