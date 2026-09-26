# Experiment Report — Candidate IMPULSE-E3 (Semantic Retrieval)

**Experiment ID:** EXP-RETRIEVAL-E3  
**Candidate Identifier:** `E3`  
**Parent Candidate:** `E2` (Git commit: `5ae9fb9449e0e576cffbf10eb25cca678cd05415`)  
**Grandparent Candidate:** `E1` (Git commit: `629414f7e5ac47726e2ec3044b021682c35402f8`)  
**Root Baseline Candidate:** `E0` (Git commit: `99c0da320af4940f4eca27d172592d1ed706d26f`, Tag: `E0-baseline`)  
**Date:** 2026-09-26  
**Status:** Candidate Defined / Structural Validation Complete / Pending Live Model Inference  
**Evidence Status:** Structural Only (No Live Inference Executed)  
**Authoritative References:** [PLAN.md](file:///E:/Projects/Impulse/PLAN.md) (Section 14, Stage 12), [semantic_retrieval.md](file:///E:/Projects/Impulse/docs/decisions/semantic_retrieval.md), [manifest.json](file:///E:/Projects/Impulse/experiments/prompts/E3/manifest.json)

---

## 1. Why E3 Exists

Candidate E3 implements **Stage 12 of PLAN.md**:
$$\text{E3} = \text{E2} + \text{semantic retrieval (\texttt{search\_similar\_code})}$$

The objective is to address localization failure modes where issue problem statements describe bugs or features using user-facing symptoms or abstract concepts that do not directly match symbol names in the codebase. In large or multi-subsystem repositories, standard text searches return either 0 results or overwhelmingly noisy matches.

E3 introduces the competition-supported `search_similar_code` tool paired with a selective retrieval controller (**Policy V1**), retaining candidate symbols in `TaskState` with concise provenance while guarding against context bloat and repetitive search loops.

---

## 2. Architectural Comparison (E2 $\to$ E3)

| Dimension | Candidate E2 | Candidate E3 |
|---|---|---|
| **Architecture Base** | Single-agent baseline with structured `TaskState` | Identical single-agent baseline + structured `TaskState` + semantic retrieval |
| **Model** | `gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` (Identical) |
| **Tools** | 6 predefined tools (`run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`) | 7 predefined tools (Preserves all 6 E2 tools + `search_similar_code`) |
| **Generation Hyperparameters** | `temperature: 0.2`, `top_p: 0.95`, `max_output_tokens: 16384`, `thinking_level: high`, `thinking_budget: 4096` | Identical generation parameters |
| **Retrieval Tooling** | None (exact shell/grep/file inspection only) | `search_similar_code(query: str, k: int = 10)` |
| **Retrieval Policy** | N/A | Selective Policy V1 (triggers on ambiguity/weak text search; initial $k=5$) |
| **Task State Continuity** | Typed `TaskState` with 11 fields | Identical `TaskState` schema, recording semantic candidates & evidence concisely |

---

## 3. Exact Prompt Delta (E2 $\to$ E3)

The prompt change between `experiments/candidates/E2/prompts/root.md` and `experiments/candidates/E3/prompts/root.md` minimally introduces selective retrieval directives under `## Operational Workflow` and Step 3:

```diff
   ## Operational Workflow
  
   Maintain structured task state across turns to ensure continuity and prevent repeated exploration:
   - Consult existing repository facts, candidate locations, and evidence before repeating exploration.
   - Keep hypotheses, evidence, and plans concise, factual, and updated as new observations emerge.
   - Track executed edits and test outcomes so previous results are not redundantly re-run.
  
+ Use semantic retrieval (`search_similar_code`) selectively:
+ - Invoke `search_similar_code` when exact search is ambiguous, when issue terms diverge from codebase symbols, or when text search returns weak candidates.
+ - Pass specific symbol or identifier names (not conversational sentences); keep initial k small (k=5).
+ - Inspect returned candidates before taking action; treat retrieval results as candidate evidence, not proof.
+ - Do not call semantic search blindly on every turn. Fall back to exact text search if semantic results are weak or empty.
+ 
   Follow a disciplined, sequential software engineering process:
  
   1. **Understand the Issue**: Carefully read the problem statement, error traces, and any provided hints. Identify the reported bug, the expected behavior, and key symbol names or error messages.
   2. **Inspect Repository State**: Check the repository structure and locate relevant modules and existing tests.
-  3. **Locate Implementation Code**: Search for the relevant functions, classes, or files using available commands and inspection tools before attempting any modifications.
+  3. **Locate Implementation Code**: Search for the relevant functions, classes, or files using available commands and inspection tools before attempting any modifications. When exact terms are ambiguous or yield weak results, use `search_similar_code` selectively.
   4. **Inspect Candidate Context**: Read the candidate source files and examine surrounding code context to understand invariants and existing conventions.
```

Steps 1–2 and 4–10 remain strictly identical. No graph-neighbor or subgraph instructions are present.

---

## 4. Semantic Retrieval Tool Contract

Inspected from authoritative source [`HARNESS_README.md`](file:///e:/Projects/Impulse/data/competition/HARNESS_README.md) Section 6.3:
- **Tool Identifier:** `search_similar_code`
- **Module:** `swegemma.tools.graph`
- **Signature:** `search_similar_code(query: str, k: int = 10) -> str`
- **Budget Gating:** Debits 1 tool call from the agent's budget.
- **Top-k Semantics:** Cosine similarity over pre-computed repository embeddings stored in `.npz` files. Nodes are sorted in descending order of similarity.
- **Node Identifier Format:** Hierarchical symbol name (e.g., `requests.adapters.HTTPAdapter`, `fastapi.routing.APIRoute`).
- **Initial $k$ Decision:** $k = 5$. This represents the smallest defensible initial breadth, offering focused candidate coverage without saturating the model's context window.

---

## 5. Retrieval Policy V1 & TaskState Integration

Implemented in [`local/retrieval/controller.py`](file:///e:/Projects/Impulse/local/retrieval/controller.py) and re-exported in [`experiments/candidates/E3/retrieval/`](file:///e:/Projects/Impulse/experiments/candidates/E3/retrieval/):
- **Selective Triggering:** Evaluates reconnaissance signals (`exact_matches_found == 0`, `has_subsystem_ambiguity`, `exact_terms_mismatch`, `text_search_weak`).
- **Anti-Spam Invariant:** Blocks consecutive blind invocations without intervening candidate inspection.
- **TaskState Integration:**
  - Retained candidate nodes (similarity $\ge 0.50$, max 3) are logged to `TaskState.candidates` with symbol name and similarity score.
  - Audit trail is appended to `TaskState.evidence`.
  - Raw code snippets (`item.code`) are discarded from `TaskState` to prevent context explosion.
- **Fallback Mechanism:** Empty responses or results below the similarity threshold ($0.50$) record fallback evidence and instruct resumption of exact search.

---

## 6. Verified Local Asset Availability

- **Graph/Embedding Assets:**
  - Neither `data/graphs/<repo>.json` nor `data/embeddings/<repo>.npz` are present in the local repository.
  - In the competition environment, these assets reside inside the official scoring image.
- **Local Execution Status:**
  - Direct execution of `search_similar_code` against real embeddings is unavailable on this Windows workstation (`execution_unavailable_local_host`).
  - No synthetic embeddings or mock relevance scores have been fabricated.

---

## 7. Evidence Status & Anti-Fabrication Notice

In accordance with **AGENTS.md Section 2.5 (Zero Fabrication)**:
1. **Zero Live Inference:** No inference has been executed on `gemma-4-31b-it-qat-w4a16-ct`.
2. **Zero Fabricated Scores:** No pass rate, fail rate, latency, or retrieval accuracy numbers are asserted (`pass_rate: null`, `fail_rate: null`).
3. **No Performance Claim:** E3 is NOT claimed to be superior to E0, E1, or E2.
4. **Scope Integrity:** Stage 13 (`get_code_neighbors`) and Stage 14 (`get_code_subgraph`) have not been implemented.
