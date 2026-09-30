# Retrieval Optimization Experiment: R1 (R1)

## Candidate Metadata
- **Candidate ID:** `R1`
- **Retrieval Variant:** `R1`
- **Policy Hash:** `121bdeee30d315b3793d6f1863fad9c27bb5136524da55f0694f47ee4818a166`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T16:58:35.710955+00:00`

## Lineage
- **Parent Candidate:** `R0`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-retrieval-r1`

## Target Failure & Hypothesis
- **Target Failure Mode:** `WRONG_FILE_LOCALIZATION`
- **Source Cluster ID:** `N/A`
- **Observation:** Agent fails to localize target files when issue terms do not match source identifiers.
> **Hypothesis:** Semantic retrieval maps natural-language problem terminology to relevant code entities.
- **Retrieval Change:** `Enable search_similar_code under controlled ambiguity trigger.`
- **Expected Metric Signal:** Reduction in wrong file localization failures.
- **Rejection Condition:** No improvement in target failure or increased failure rate.

## Retrieval Policy Diff
### Policy Diff: `R0` (R0) -> `R1` (R1)

- **Parent Policy Hash:** `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7`
- **Candidate Policy Hash:** `121bdeee30d315b3793d6f1863fad9c27bb5136524da55f0694f47ee4818a166`
- **Identical:** `NO`

#### Enabled Features
- `semantic_retrieval_enabled`: `False` -> `True`

#### Budgets & Limits
- `max_retrieval_calls`: `0` -> `3`
- `max_semantic_calls`: `0` -> `3`
- `max_retrieved_items`: `0` -> `15`

#### Parameters & Depth
- `semantic_top_k`: `0` -> `5`
- `expansion_policy`: `none` -> `semantic_only`

#### Trigger Conditions
- `allow_file_inspection`: `True` -> `None`
- `allow_text_search`: `True` -> `None`
- `min_similarity`: `None` -> `0.5`
- `require_exact_ambiguity`: `None` -> `True`
- `semantic_enabled`: `False` -> `None`


## Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `WRONG_FILE_LOCALIZATION`
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
- `metrics.json`: `1e328b1bf90745c4794f8a5ca24d598bd8277c2cc448b50357d33a64c1a34fc7`
- `policy.json`: `a8e6150faf89b8f5ab3326acd8080fcda83c0a0bc4d36b8ade8d86b2ac4f4675`
- `retrieval_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`