# IMPULSE — Retrieval Optimization Loop (Stage 33)

This document establishes the architecture, policy specifications, execution framework, and evaluation standards for the **Retrieval Optimization Loop** in IMPULSE.

---

## 1. Purpose

The central research and engineering question of Stage 33 is:

> *“Which retrieval strategy provides the best task-solving evidence per unit of retrieval cost?”*

In repository-level issue resolution, more retrieval is not automatically better. Over-expansion can flood the model's limited context window with tangential code, causing distraction, increasing latency, and exhausting token budgets. Conversely, under-expansion leaves the agent struggling with missing definitions or unobserved caller-callee interactions.

The Retrieval Optimization Loop establishes an empirical, reproducible framework to compare controlled retrieval variants (**R0 through R4**) on both **Quality** and **Cost**, maintaining single-dimension isolation without contaminating prompts, multi-agent topology, or competition tool contracts.

---

## 2. Core Retrieval Variants (R0–R4)

All retrieval operations strictly utilize the competition tools defined in the competition harness:
- `search_similar_code`
- `get_code_neighbors`
- `get_code_subgraph`

No external or simulated vector databases are invented.

### R0 — Baseline (No Semantic/Graph Retrieval)
- **Concept:** Disables semantic search and graph-traversal optimization tools while preserving normal, disciplined repository reconnaissance (exact grep, file directory exploration, and targeted source reading).
- **Tool Access:** `search_similar_code` = OFF, `get_code_neighbors` = OFF, `get_code_subgraph` = OFF.
- **Role:** Pure non-semantic control baseline against which all graph/embedding improvements are measured.

### R1 — Semantic Retrieval
- **Concept:** Enables `search_similar_code` under a controlled activation policy.
- **Trigger Conditions:** Triggered when exact grep returns zero or ambiguous matches, or when problem issue terminology diverges from repository symbols.
- **Policy Bounds:** Small top-k ($k = 5$), similarity threshold ($\ge 0.50$), max 3 calls per task.
- **Recorded Provenance:** Query text, returned node IDs, accepted vs. discarded candidates, execution duration, and subsequent source inspections.

### R2 — Semantic Retrieval + Selective Code Neighbors
- **Concept:** Introduces `get_code_neighbors` after semantic retrieval identifies a promising symbol.
- **Expected Flow:**
  $$\text{Issue Recon} \longrightarrow \text{Semantic Search} \longrightarrow \text{Inspect Candidate} \longrightarrow \text{Selective Neighbors} \longrightarrow \text{Targeted Source Reads}$$
- **Policy Bounds:** Depth 1 expansion, maximum 3 neighbor expansions per task, bounded candidate retention ($k \le 5$). Never expands uninspected symbols.

### R3 — Semantic Retrieval + Selective Subgraph
- **Concept:** Introduces `get_code_subgraph` when multiple connected candidate symbols require relational dependency disambiguation.
- **Trigger Conditions:** Activated only after $\ge 2$ related symbols have been inspected and caller/callee or class hierarchy relationships remain unresolved.
- **Policy Bounds:** Bounded candidate breadth ($k \in \{2, 4, 8\}$), depth 1, max 2 subgraph calls per task.

### R4 — Dynamic Retrieval Depth
- **Concept:** An adaptive, evidence-driven retrieval control strategy.
- **Control Loop:**
  $$\text{Start Small} \longrightarrow \text{Evaluate Evidence} \longrightarrow \begin{cases} \text{Sufficient} \longrightarrow \text{STOP} \\ \text{Uncertain} \longrightarrow \text{Expand Next Relational Layer} \\ \text{Redundant / Budget Exhausted} \longrightarrow \text{STOP} \end{cases}$$
- **Observable Stopping Signals:**
  1. Exact candidate symbol located and verified against issue requirements.
  2. Caller/callee dependency paths resolved.
  3. No new unique entities surfaced by subsequent calls ($\ge 50\%$ redundancy).
  4. Configured task retrieval budget reached.
- **Observability:** Records structured `DynamicRoundTrace` for each round without exposing private chain-of-thought.

---

## 3. Retrieval Policy Model

Every retrieval configuration is governed by a typed, immutable `RetrievalPolicy` dataclass:
- `semantic_retrieval_enabled`: boolean flag
- `neighbor_retrieval_enabled`: boolean flag
- `subgraph_retrieval_enabled`: boolean flag
- `dynamic_depth_enabled`: boolean flag
- `semantic_top_k`: integer (default 5, valid 1..50)
- `neighbor_depth`: integer (default 1)
- `subgraph_depth`: integer (default 1)
- `subgraph_breadth_k`: integer (supported 2, 4, 8)
- `max_retrieval_calls`: total retrieval invocation limit
- `max_semantic_calls`, `max_neighbor_calls`, `max_subgraph_calls`: per-tool budgets
- `similarity_threshold`: minimum cosine similarity cutoff
- `trigger_conditions`: explicit activation triggers
- `dynamic_config`: adaptive depth parameters (min/max depth, max rounds, redundancy stop threshold)
- `fallback_behavior`: structured graceful degradation rules

Every policy generates an authoritative SHA-256 hash (`retrieval_policy_hash`) over its canonical sorted parameters.

---

## 4. Single-Dimension Isolation & Invariance

Stage 33 adheres strictly to the single-intervention discipline established in Stage 31 (FDD) and Stage 32 (Prompt Optimization):
1. **Prompt Invariance:** The root prompt is strictly frozen to the immutable `P0` baseline (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`).
2. **Topology Invariance:** Fixed to the baseline `root_only` topology. No Scout, Debugger, or Reviewer specialists are introduced or modified.
3. **Model Invariance:** Fixed to the competition model `gemma-4-31b-it-qat-w4a16-ct`.
4. **Tool Contract Invariance:** Exactly matching the competition specification (`search_similar_code`, `get_code_neighbors`, `get_code_subgraph`).
5. **Frozen Baseline Verification:** All 14 frozen artifacts from Stage 24 are verified for byte-for-byte invariance before any experiment is promoted.

---

## 5. Quantitative Cost and Quality Metrics

To prevent subjective optimization, Stage 33 records and reports independent Quality and Cost dimensions without collapsing them into an opaque single score.

### Cost Metrics
- `retrieval_call_count`: Total retrieval invocations (broken down by semantic, neighbor, subgraph)
- `retrieval_tool_call_share`: Ratio of retrieval calls to total agent tool calls
- `retrieval_duration_ms`: Mean, median, and p95 latency
- `retrieved_entities`: Total symbols and nodes returned
- `unique_entities` vs `duplicate_entities`: Redundancy tracking
- `source_files_exposed`: Unique source files touched or surfaced by retrieval
- `total_context_growth_tokens`: Pre-compaction retrieval context expansion
- `cache_hit_count` and `cache_hit_ratio`: Hit rate from Stage 26 bounded tool cache
- **Information-Gain Proxies:**
  $$\text{Entity Gain Proxy} = \frac{\text{Unique Entities Exposed}}{\text{Retrieval Calls}}$$
  $$\text{File Gain Proxy} = \frac{\text{Unique Source Files Exposed}}{\text{Retrieval Calls}}$$

### Quality Metrics
- `pass_rate` and `failure_rate`
- `targeted_failure_count` and `targeted_failure_rate`
- `localization_failure_count`: Failures specifically attributed to wrong file or missing symbol localization
- `clean_copy_verification_success`: Verification in isolated clean-copy evaluation clone
- `recovery_success_count`: Recovery transitions initiated from retrieval fallbacks

### Quality / Cost Frontier Matrix
Candidates are compared transparently along Pareto dimensions:
```
Variant | Candidate | Pass Rate | Target Failures | Retrieval Calls | Mean Duration (ms) | Unique Entities | Context Growth | Cache Hit % | Info Gain Proxy
```

---

## 6. Paired Task Comparisons

Evaluations on identical benchmark splits perform per-task paired outcome analysis:
- `FAIL_TO_PASS`: Task failed under baseline, resolved under candidate.
- `PASS_TO_FAIL`: Regression; task solved under baseline, failed under candidate.
- `FAIL_TO_OTHER_FAIL`: Failure category shifted.
- `FAIL_UNCHANGED`: Unresolved failure without category shift.
- `PASS_UNCHANGED`: Retained success.

For each task, paired comparisons record the exact change in retrieval behavior (call counts, tools called, unique nodes discovered).

---

## 7. Retrieval Diagnostics & Pathology Detection

The trace engine automatically monitors and flags retrieval pathologies:
1. **Redundancy:** Repeated identical queries or duplicate result sets within a run.
2. **Dead Retrieval:** Entities retrieved from tools but never subsequently read or inspected.
3. **Over-Expansion:** Large result sets ($\ge 8$ entities) followed by $\le 1$ entity inspection.
4. **Under-Expansion:** Task failure where relevant connected symbols were never retrieved.
5. **Late Retrieval:** Retrieval invocations executed only after file mutations have already occurred.
6. **Misleading Retrieval:** Retrieved candidates that diverted investigation away from the true fault location.

---

## 8. Integration with Prior Stages

### Stage 25 (Context Compaction) Interaction
Stage 25 context compaction rules remain intact and unchanged. Retrieval metrics record pre-compaction retrieval expansion accurately to measure raw retrieval footprint, while post-compaction context conforms to standard token budgets.

### Stage 26 (Tool-Call Budgeting & Bounded Caching) Interaction
Retrieval operations utilize the Stage 26 `BoundedToolCache`:
- Repeated queries with identical parameters and repository state IDs are served directly from cache.
- Cache hits increment `cache_hit_count` and are accounted for with zero external latency and zero fresh API calls.
- Cache operations are explicitly reported and not conflated with external tool calls.

### Stage 31 (Failure-Driven Development Loop) Interaction
Retrieval interventions originate directly from observed failure clusters where `intervention_scope == "RETRIEVAL"`:
$$\text{Cluster Selection} \longrightarrow \text{Hypothesis Formulation} \longrightarrow \text{Policy Diff} \longrightarrow \text{Smoke/Validation/Held-Out Gating}$$

---

## 9. Fallback Behavior and Graceful Degradation

If a retrieval tool fails or external dependencies are unavailable:
- **Semantic Search Error:** Falls back gracefully to exact keyword and text reconnaissance without aborting the task.
- **Neighbor Expansion Error:** Proceeds with direct inspection of already-identified symbols.
- **Subgraph Error:** Uses local symbol context without induced graph expansion.
- **Budget Exhaustion:** Halts retrieval immediately and directs agent to synthesize fixes from current evidence.

---

## 10. Fixture Mode & Honest Local Evaluation

Because competition-scale Gemma 4 31B inference is unavailable on the local Windows development host, Stage 33 maintains strict separation of evidence modes:
- **FIXTURE Mode:** Deterministic synthetic fixtures (**A through T**) prove the correctness, edge-case resilience, and diagnostic reporting of the retrieval optimization loop.
- **LIVE Mode / Real Data:** Baseline runs in `experiments/baseline/E0` reflect real infrastructure unavailability (`NO_ACTIONABLE_LIVE_FAILURES`).
- **Zero Fabrication:** No synthetic improvement is asserted as real-world agent performance. Candidates evaluated without real inference are labeled `decision = INCONCLUSIVE` or `NO_ACTIONABLE_DATA`.
