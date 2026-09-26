# Architectural Decision Record: Semantic Retrieval (search_similar_code) — IMPULSE

**Status:** Accepted  
**Date:** 2026-09-26  
**Decision Makers:** IMPULSE Architecture Team  
**Consulted Documents:**
- [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) (Section 14, Stage 12)
- [HARNESS_README.md](file:///e:/Projects/Impulse/data/competition/HARNESS_README.md) (Sections 5.2, 6.3)
- [tool_contracts.md](file:///e:/Projects/Impulse/docs/decisions/tool_contracts.md) (Section 3.8)
- [structured_task_state.md](file:///e:/Projects/Impulse/docs/decisions/structured_task_state.md)

---

## 1. Context & Problem Statement

In Candidate E2, IMPULSE introduced structured `TaskState` to maintain turn-to-turn continuity and track hypotheses, candidate locations, and evidence. However, candidate localization in E2 relied strictly on exact keyword search and file inspection via shell commands or `read_file`.

When issue descriptions do not match code symbol names (e.g., conceptual bug reports, high-level behavioral errors, or multi-subsystem repositories), exact keyword searches often return 0 results or flood the context with irrelevant substring hits.

To address this, the competition platform provides code graph intelligence tools. Candidate E3 introduces the first retrieval tool:
$$\text{E3} = \text{E2} + \text{semantic retrieval (\texttt{search\_similar\_code})}$$

---

## 2. Tool Contract: `search_similar_code`

From authoritative inspection of `HARNESS_README.md` (Section 6.3) and `swegemma.tools.graph`:

### 2.1. Signature & Parameters
```python
search_similar_code(query: str, k: int = 10) -> str
```
- **`query`** (`str`, required): Symbol, function, class, or module identifier name.
  - *Offline Constraint*: In the competition scoring container, the environment is offline without a live neural embedding server. Queries must be symbol or identifier names (e.g., `"HTTPConnection"`, `"parse_header"`, `"APIRoute"`), rather than conversational sentences.
- **`k`** (`int`, optional, default `10`): Number of nearest neighbor nodes to return, bounded in the range $[1, 50]$.
- **Budget Gating**: Annotated with `@budget_gated(count_tool_call=True)`. Each invocation debits the `tool_calls` budget by **1**.

### 2.2. Return Schema
Returns a serialized JSON string:
```json
{
  "status": "ok",
  "query": "HTTPConnection",
  "results": [
    {
      "node_name": "requests.adapters.HTTPAdapter",
      "code": "class HTTPAdapter(BaseAdapter):\n...",
      "similarity": 0.9412
    }
  ],
  "count": 1
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

## 3. Initial $k$ Decision

**Decision:** Choose initial $k = 5$.

### Rationale:
1. **Contract Support**: The tool contract specifies a default of `10` and accepts $1 \le k \le 50$. An initial $k=5$ is fully supported by the contract.
2. **Context Economy**: Each returned item contains code signatures/docstrings. Returning 10 items would consume 2,000–4,000 tokens of the model's 32,768 context window. Returning $k=5$ provides sufficient localization breadth while preserving context for multi-turn reasoning.
3. **Smallest Defensible Breadth**: Per PLAN.md Stage 12 ("keep initial $k$ small; inspect returned candidates before expanding"), $k=5$ provides the tightest defensible set of suspect symbols.

---

## 4. Retrieval Policy v1

Semantic retrieval is **budget-gated** and must not be invoked indiscriminately on every turn.

### 4.1. Trigger Conditions
Invoke `search_similar_code` **only** when one or more of the following conditions hold:
1. **Term Mismatch**: Exact terms from the problem statement (e.g., user-facing error strings, conceptual bug names) fail to match identifiers in the codebase.
2. **Weak Candidates**: Initial keyword or grep searches return 0 matches or only low-relevance test matches.
3. **Subsystem Ambiguity**: The repository contains multiple candidate subsystems and cheap exact searches fail to identify which subsystem implements the behavior.
4. **Large Repository**: The codebase is large enough that manual top-level directory inspection cannot locate candidate symbols.

### 4.2. Non-Calling Invariants
The policy must **NOT** invoke semantic retrieval when:
1. Exact reconnaissance has already identified the target file and function with high confidence.
2. The agent has already called semantic retrieval on the immediately preceding turn without first inspecting the returned candidates (preventing blind polling loops).
3. The fix is already in progress (editing or verification phases).

### 4.3. Information-Gain Flow
```text
Issue
  ↓
Cheap exact search / normal reconnaissance
  ↓
If ambiguity or weak candidates
  ↓
search_similar_code(query, k=5)
  ↓
Inspect returned candidate symbols/nodes
  ↓
Select relevant candidates → TaskState
  ↓
Continue source inspection (read_file)
```

---

## 5. TaskState Integration

Per Stage 11 and Stage 12 specifications, TaskState is updated with concise provenance and **must not** store raw code payloads or full multi-KB JSON dumps.

1. **Candidates Table (`TaskState.candidates`)**:
   - `path`: Derived file path or symbol identifier.
   - `symbol`: `node_name` (e.g., `"requests.adapters.HTTPAdapter"`).
   - `line_number`: `None` (resolved later during source inspection).
   - `rationale`: `"Semantic match for query '<query>' (similarity: 0.9412)"`.
2. **Evidence Table (`TaskState.evidence`)**:
   - `observation`: `"Semantic search '<query>' returned symbol '<node_name>' (similarity: 0.9412)"`.
   - `source_command_or_file`: `"search_similar_code(query='<query>', k=5)"`.
   - `supports_hypothesis`: `None` (candidate evidence awaiting manual inspection).
3. **Cap & Pruning**:
   - The policy retains at most 3 top-scoring candidates with similarity $\ge 0.50$.
   - Full code snippets from `results[].code` are discarded from `TaskState`; the agent inspects source via `read_file`.

---

## 6. Fallback Behavior

If `search_similar_code`:
1. Returns zero results (`count == 0`), or
2. All returned similarities fall below the weak-similarity threshold ($\text{similarity} < 0.50$), or
3. Fails with a tool error:

The retrieval controller:
- Records a neutral evidence item noting the weak/empty semantic search result.
- Sets `fallback_triggered = True`.
- Instructs the agent to fall back to exact text search, file pattern matching (`find`, `grep`), and test-driven localization.

---

## 7. Execution Boundary & Anti-Fabrication Notice

1. **Local Workstation Status**:
   - The repository embedding archive (`data/embeddings/<repo>.npz`) and dependency graph (`data/graphs/<repo>.json`) are pre-computed only inside the Kaggle competition scoring image and are not distributed in the local development repository.
   - Live vLLM serving with `gemma-4-31b-it-qat-w4a16-ct` is not available on this workstation.
2. **Structural Validation Only**:
   - E3 is validated structurally (configuration schemas, prompt deltas, policy behavior, and TaskState integration tests).
   - No benchmark pass rates, resolution metrics, or fake embedding results are fabricated (`pass_rate: null`).
