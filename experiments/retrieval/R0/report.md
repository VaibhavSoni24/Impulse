# Retrieval Optimization Experiment: R0 (R0)

## Candidate Metadata
- **Candidate ID:** `R0`
- **Retrieval Variant:** `R0`
- **Policy Hash:** `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T16:58:18.131579+00:00`

## Lineage
- **Parent Candidate:** `None (Root Baseline)`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-retrieval-r0-baseline`

## Target Failure & Hypothesis
- **Target Failure Mode:** `BASELINE`
- **Source Cluster ID:** `N/A`
- Baseline specification (no active intervention hypothesis).

## Retrieval Policy Diff
### Policy Diff: `R0` (R0) -> `R0` (R0)

- **Parent Policy Hash:** `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7`
- **Candidate Policy Hash:** `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7`
- **Identical:** `YES`

No policy parameters were changed.

## Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `BASELINE`
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
- **Validation Gate:** PASSED
- **Held-Out Gate:** UNEXECUTED (held-out protected)
- **Authoritative Decision:** `PROMOTED`
- **Decision Rationale:** Immutable baseline R0 established (no semantic/graph retrieval).

## Artifact Hashes
- `metrics.json`: `e9d5e62dbaa55bdb25ab76e707e84df8d887442618f86a695e05d7402cd65da1`
- `policy.json`: `e1611a2ce4e00ddc0f28b2ed812d5e85f56d2c0572257741a3a5486cad2e2257`
- `retrieval_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`