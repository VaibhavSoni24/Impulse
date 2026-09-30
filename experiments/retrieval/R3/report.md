# Retrieval Optimization Experiment: R3 (R3)

## Candidate Metadata
- **Candidate ID:** `R3`
- **Retrieval Variant:** `R3`
- **Policy Hash:** `2328f01cb2b834aa8a220bf64c9d19608e63f95ebd5e0a8623ad8843e6187ce1`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T16:58:35.765499+00:00`

## Lineage
- **Parent Candidate:** `R2`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-retrieval-r3`

## Target Failure & Hypothesis
- **Target Failure Mode:** `UNRESOLVED_MULTI_SYMBOL_DEPENDENCY`
- **Source Cluster ID:** `N/A`
- **Observation:** Multi-class interaction requires understanding induced subgraph between candidate symbols.
> **Hypothesis:** Selective subgraph retrieval establishes paths between connected candidate symbols.
- **Retrieval Change:** `Enable get_code_subgraph selectively for multi-symbol interactions.`
- **Expected Metric Signal:** Resolution of multi-symbol dependency failures.
- **Rejection Condition:** Over-expansion or increased tool timeouts.

## Retrieval Policy Diff
### Policy Diff: `R2` (R2) -> `R3` (R3)

- **Parent Policy Hash:** `0b792bbf15a3a4026052a4ea8d8464fd972546feaeb21b898e693c923509ba1a`
- **Candidate Policy Hash:** `2328f01cb2b834aa8a220bf64c9d19608e63f95ebd5e0a8623ad8843e6187ce1`
- **Identical:** `NO`

#### Enabled Features
- `subgraph_retrieval_enabled`: `False` -> `True`

#### Budgets & Limits
- `max_retrieval_calls`: `5` -> `6`
- `max_neighbor_calls`: `3` -> `2`
- `max_subgraph_calls`: `0` -> `2`
- `max_retrieved_items`: `20` -> `25`

#### Parameters & Depth
- `subgraph_depth`: `0` -> `1`
- `subgraph_breadth_k`: `0` -> `4`
- `expansion_policy`: `selective_neighbors` -> `selective_subgraph`

#### Trigger Conditions
- `require_multi_symbol_relation`: `None` -> `True`

#### Fallback Behavior
- `on_subgraph_failure`: `None` -> `INSPECT_CURRENT_SYMBOLS`


## Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `UNRESOLVED_MULTI_SYMBOL_DEPENDENCY`
- **Target Failure Count:** 0
- **Target Failure Rate:** 0.00%
- **Localization Failures:** 0
- **Clean-Copy Verification:** PASSED
- **Recovery Successes:** 0

## Cost Metrics
- **Retrieval Call Count:** 0
  - Semantic Calls: 0
  - Neighbor Calls: 0
  - Subgraph Calls: 0
- **Retrieval Tool-Call Share:** N/A
- **Mean Duration:** N/A
- **Median Duration:** N/A
- **p95 Duration:** N/A
- **Retrieved Entities (Total):** 0
- **Unique Entities:** 0
- **Duplicate Entities:** 0
- **Source Files Exposed:** 0
- **Context Growth:** N/A
- **Cache Hits:** 0 (N/A)
- **Info Gain Proxy (Entities/Call):** N/A
- **Info Gain Proxy (Files/Call):** N/A

## Retrieval Diagnostics
- **Redundancy Count:** 0
- **Dead Retrieval Count:** 0
- **Over-Expansion Count:** 0
- **Under-Expansion Count:** 0
- **Late Retrieval Count:** 0
- **Misleading Retrieval Count:** 0

## Paired Task Comparison
- No paired baseline comparison executed.

## Evaluation Gates
- **Smoke Gate:** SKIPPED
- **Validation Gate:** UNEXECUTED
- **Held-Out Gate:** UNEXECUTED (held-out protected)
- **Authoritative Decision:** `INCONCLUSIVE`
- **Decision Rationale:** Live inference unavailable locally on Windows host.

## Artifact Hashes
- `metrics.json`: `27a20dc38881c4d404528545548262fc9673f19c6d5f5c78a90cd493ebce2e7d`
- `policy.json`: `711f64fabadb80904782f9d7f3fc3e29a735d5daf3dfa873a9e642767550b582`
- `retrieval_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`