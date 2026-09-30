# Retrieval Optimization Experiment: R4 (R4)

## Candidate Metadata
- **Candidate ID:** `R4`
- **Retrieval Variant:** `R4`
- **Policy Hash:** `b9d21f1414d2a18e97a30adf38b19754ff6249eed4ffb12ca95ba0e4c3cdfee8`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T16:58:35.783430+00:00`

## Lineage
- **Parent Candidate:** `R3`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-retrieval-r4`

## Target Failure & Hypothesis
- **Target Failure Mode:** `RETRIEVAL_OVER_UNDER_EXPANSION`
- **Source Cluster ID:** `N/A`
- **Observation:** Fixed-depth retrieval either over-expands simple tasks or under-expands complex multi-file tasks.
> **Hypothesis:** Adaptive retrieval depth with early stopping balances localization quality against context cost.
- **Retrieval Change:** `Enable dynamic retrieval depth with evidence sufficiency checks and redundancy stops.`
- **Expected Metric Signal:** Lower average retrieval calls and preserved/improved pass rate on complex tasks.
- **Rejection Condition:** Redundant expansion loops or failure to terminate early when evidence is sufficient.

## Retrieval Policy Diff
### Policy Diff: `R3` (R3) -> `R4` (R4)

- **Parent Policy Hash:** `2328f01cb2b834aa8a220bf64c9d19608e63f95ebd5e0a8623ad8843e6187ce1`
- **Candidate Policy Hash:** `b9d21f1414d2a18e97a30adf38b19754ff6249eed4ffb12ca95ba0e4c3cdfee8`
- **Identical:** `NO`

#### Enabled Features
- `dynamic_depth_enabled`: `False` -> `True`

#### Budgets & Limits
- `max_retrieval_calls`: `6` -> `8`
- `max_semantic_calls`: `2` -> `3`
- `max_neighbor_calls`: `2` -> `3`
- `max_retrieved_items`: `25` -> `30`

#### Parameters & Depth
- `subgraph_depth`: `1` -> `2`
- `expansion_policy`: `selective_subgraph` -> `dynamic_adaptive`

#### Trigger Conditions
- `adaptive_uncertainty`: `None` -> `True`
- `require_multi_symbol_relation`: `True` -> `None`
- `require_promising_symbol`: `True` -> `None`

#### Dynamic Expansion Config
- `confidence_threshold`: `None` -> `0.75`
- `max_rounds`: `3` -> `4`


## Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `RETRIEVAL_OVER_UNDER_EXPANSION`
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
- `metrics.json`: `57a2c8840d14a933cb5ca306671753630ae47d97450313d2b4d6d5d2e13cfc7e`
- `policy.json`: `06da2941cb6ad668c827ec82d7eb6074581f2470632eb064582752f6cf17a4ae`
- `retrieval_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`