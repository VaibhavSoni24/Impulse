# Testing Strategy Experiment: T3 (T3)

## Candidate Metadata
- **Candidate ID:** `T3`
- **Testing Variant:** `T3`
- **Policy Hash:** `033142e460c9db117c6dcca70d7ceb306c2d4e172243d164a84b4e367ef343f9`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Retrieval Policy Hash:** `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7`
- **Test Skill Hash:** `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148`
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T17:23:58.314036+00:00`

## Lineage
- **Parent Candidate:** `T2`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-testing-t3`

## Target Failure & Hypothesis
- **Target Failure Mode:** `FALSE_CONFIDENCE`
- **Source Cluster ID:** `N/A`
- **Observation:** Fixed test suites either over-test low-risk changes or under-test high-risk architectural changes.
> **Hypothesis:** Adaptive test escalation based on observable risk signals dynamically optimizes evidence yield against execution cost.
- **Testing Change:** `Enable rule-based adaptive escalation (TARGETED -> ADJACENT -> SUBSYSTEM -> FULL) driven by explicit risk signals.`
- **Expected Metric Signal:** High-risk changes receive broader validation; low-risk changes terminate early with minimal test commands.
- **Rejection Condition:** Adaptive escalation fails to stop on low-risk tasks or fails to escalate on observed high-risk signals.

## Testing Policy Diff
### Testing Policy Diff: `T2` (T2) -> `T3` (T3)

- **Parent Policy Hash:** `cada62c1b0291ee4db996080671bf80b0249a21f810171fd17c21a91cd739d25`
- **Candidate Policy Hash:** `033142e460c9db117c6dcca70d7ceb306c2d4e172243d164a84b4e367ef343f9`
- **Identical:** `NO`

#### Enabled Strategy Levels
- `adaptive_enabled`: `False` -> `True`

#### Escalation Rules
- `escalate_on_incomplete_fix`: `None` -> `True`

#### Stopping Rules
- `stop_on_adjacent_pass_if_no_regressions`: `False` -> `True`
- `stop_on_targeted_pass_if_low_risk`: `False` -> `True`


## Evidence & Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `FALSE_CONFIDENCE`
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
- **Testing Tool-Call Share:** N/A

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
- **Validation Gate:** UNEXECUTED
- **Held-Out Gate:** UNEXECUTED (held-out protected)
- **Authoritative Decision:** `INCONCLUSIVE`
- **Decision Rationale:** Live inference unavailable locally on Windows host.

## Artifact Hashes
- `metrics.json`: `2142d406a077e374ef372dab0a7bec7a610faee65b496ffcebe1b179292e4723`
- `policy.json`: `3b5b59653aaea82f9f8427990c913554b95c25f3cf18ad52780f11e38b1c7c21`
- `policy_diff.json`: `307bf735c1eac8e1d7edf77cc2ce960e4751b67781964acd8556dca38f1ff67e`
- `policy_diff.md`: `f41c496fa0ffe5720feec0e4596be2e302dc7f1d186ad9fc0c98660062090962`
- `test_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`