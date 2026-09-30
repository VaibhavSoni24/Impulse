# Retrieval Optimization Experiment: R2 (R2)

## Candidate Metadata
- **Candidate ID:** `R2`
- **Retrieval Variant:** `R2`
- **Policy Hash:** `0b792bbf15a3a4026052a4ea8d8464fd972546feaeb21b898e693c923509ba1a`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T16:58:35.735320+00:00`

## Lineage
- **Parent Candidate:** `R1`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-retrieval-r2`

## Target Failure & Hypothesis
- **Target Failure Mode:** `MISSING_CALLER_CONTEXT`
- **Source Cluster ID:** `N/A`
- **Observation:** Agent identifies seed symbol but misses direct caller/callee relationships necessary for the fix.
> **Hypothesis:** Selective neighbor retrieval surfaces incoming and outgoing symbol relations without bloating context.
- **Retrieval Change:** `Enable get_code_neighbors selectively after inspecting seed symbol.`
- **Expected Metric Signal:** Reduction in missing context failures.
- **Rejection Condition:** Context explosion or zero new useful entities.

## Retrieval Policy Diff
### Policy Diff: `R1` (R1) -> `R2` (R2)

- **Parent Policy Hash:** `121bdeee30d315b3793d6f1863fad9c27bb5136524da55f0694f47ee4818a166`
- **Candidate Policy Hash:** `0b792bbf15a3a4026052a4ea8d8464fd972546feaeb21b898e693c923509ba1a`
- **Identical:** `NO`

#### Enabled Features
- `neighbor_retrieval_enabled`: `False` -> `True`

#### Budgets & Limits
- `max_retrieval_calls`: `3` -> `5`
- `max_semantic_calls`: `3` -> `2`
- `max_neighbor_calls`: `0` -> `3`
- `max_retrieved_items`: `15` -> `20`

#### Parameters & Depth
- `neighbor_depth`: `0` -> `1`
- `expansion_policy`: `semantic_only` -> `selective_neighbors`

#### Trigger Conditions
- `require_promising_symbol`: `None` -> `True`

#### Fallback Behavior
- `on_neighbor_failure`: `None` -> `INSPECT_CURRENT_SYMBOLS`


## Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `MISSING_CALLER_CONTEXT`
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
- `metrics.json`: `295c8ea684929c936e87fa2716fddf8b2e32adf424b7afe8a2255489598ecc12`
- `policy.json`: `fac16b321ea1e59efb836171ee0810cb6b65974f2da4ad2287e3d8d3c0fc85a0`
- `retrieval_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`