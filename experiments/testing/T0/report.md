# Testing Strategy Experiment: T0 (T0)

## Candidate Metadata
- **Candidate ID:** `T0`
- **Testing Variant:** `T0`
- **Policy Hash:** `76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Retrieval Policy Hash:** `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7`
- **Test Skill Hash:** `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148`
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T17:22:59.871602+00:00`

## Lineage
- **Parent Candidate:** `None (Root Baseline)`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-testing-t0-baseline`

## Target Failure & Hypothesis
- **Target Failure Mode:** `BASELINE`
- **Source Cluster ID:** `N/A`
- Baseline specification (no active intervention hypothesis).

## Testing Policy Diff
### Testing Policy Diff: `T0` (T0) -> `T0` (T0)

- **Parent Policy Hash:** `76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36`
- **Candidate Policy Hash:** `76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36`
- **Identical:** `YES`

No testing policy parameters were changed.

## Evidence & Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `BASELINE`
- **Target Failure Count:** 0
- **Target Failure Rate:** 0.00%
- **Regressions Caught:** 0
- **Incomplete Fixes Caught:** 0
- **Targeted Behavior Confirmed:** 0
- **Adjacent Failures Discovered:** 0
- **Subsystem Failures Discovered:** 0
- **Full Suite Failures Discovered:** 0
- **False-Confidence Cases Avoided:** 0
- **Earliest Detection Level:** `NONE`
- **Clean-Copy Verification:** PASSED

## Cost Metrics
- **Total Test Commands:** 0
  - Targeted Commands: 0
  - Adjacent Commands: 0
  - Subsystem Commands: 0
  - Full Suite Commands: 0
- **Total Test Cases Executed:** 0
- **Total Test Runtime:** 0.0 ms
- **Mean Test Duration:** N/A
- **Median Test Duration:** N/A
- **p95 Test Duration:** N/A
- **Total Output Volume:** 0 bytes
- **Repeated Commands:** 0
- **Duplicate Test Cases:** 0
- **Testing Tool-Call Share:** 0.0%

## Testing Diagnostics
- **Duplicate Commands:** 0
- **Duplicate Test Cases:** 0
- **Reruns Without Edit:** 0
- **Unnecessary Full Suites:** 0
- **Zero-New-Evidence Adjacent Runs:** 0
- **Zero-New-Evidence Subsystem Runs:** 0
- **Repeated Identical Failures:** 0

## Paired Task Comparison
- No paired baseline comparison executed.

## Evaluation Gates
- **Smoke Gate:** SKIPPED
- **Validation Gate:** PASSED
- **Held-Out Gate:** UNEXECUTED (held-out protected)
- **Authoritative Decision:** `PROMOTED`
- **Decision Rationale:** Immutable baseline T0 established (minimal targeted test execution).

## Artifact Hashes
- `metrics.json`: `260b82f18876ce957286e1edae5a4bff77eeec3f3ff3b265e1c1bb612a2421b5`
- `policy.json`: `6e9c117ed9abc6c9c3a806b2aa5e37c1b0116ddc076ec1b99f1fc75e641462a3`
- `test_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`