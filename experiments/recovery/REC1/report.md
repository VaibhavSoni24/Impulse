# Recovery Optimization Experiment Report: Candidate `REC1`

## Candidate Metadata
- **Candidate ID:** `REC1`
- **Parent Candidate:** `REC0`
- **Policy Hash:** `4e8f53a7b9ce4aa364dba5b8433a37e59ab37725ade02e63b9c5b47479b3c980`
- **Evidence Mode:** `FIXTURE`
- **Benchmark Split:** `dev`
- **Promotion Decision:** `REJECTED`
- **Decision Rationale:** Targeted failure mode remained unchanged at 2 failures.

## Invariance Verification
- **Root Prompt Hash:** `2360d4bf64dd...` (Invariant)
- **Retrieval Policy Hash:** `3e1b234a2ac7...` (Invariant R0)
- **Testing Policy Hash:** `76820d5c5e2a...` (Invariant T0)
- **Topology:** `root_only` (Invariant)
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct` (Invariant)
- **Test Strategy Skill:** `3d027b0f9a7f...` (Frozen)
- **Repo Triage Skill:** `ac7a967136bb...` (Frozen)

## Causal Recovery Hypothesis
- **Target Failure:** `auth token expired`
- **Observation:** Targeted failure pattern observed in baseline.
- **Hypothesis:** Recovery intervention resolves failure earlier and reliably.
- **Recovery Change:** Adopt REC1 policy parameters.
- **Expected Signal:** Target failure reduction > 0, zero loop regression.
- **Rejection Condition:** New recovery loops or collateral regressions.

## Recovery Quality & Effectiveness
| Metric | Value |
| :--- | :--- |
| Targeted Recovery Success Rate | 0.0% |
| Targeted Failure Reduction | 0 tasks |
| Recovery Loop Count | 0 |
| Detection Latency (Events) | 0.0 |
| Detection Latency (Turns) | 0.0 |
| Average Recovery Attempts | 1.00 |
| Tasks Recovered After Failure | 0 |
| Tasks Abandoned After Failure | 2 |
| Alternate Path Success Rate | 0.0% |
| First-Attempt Success Rate | 0.0% |

## Resource & Recovery Cost Metrics
| Metric | Value |
| :--- | :--- |
| Total Recovery Tool Calls | 0 |
| Recovery Turns Used | 1 |
| Total Retries Executed | 0 |
| Total Recovery Runtime | 0.0 ms |
| Additional Tests Caused | 0 |
| Additional Retrievals Caused | 0 |
| Additional Context Growth | 0 bytes |
| Repeated Failed Interventions | 2 |

## Deterministic Diagnostics
- **Late Recovery:** `NO`
- **Repeated Identical Recovery:** `YES`
- **Recovery Oscillation:** `NO`
- **Retry Waste:** `NO`
- **Recovery Without State Change:** `YES`
- **Missed Recovery Opportunity:** `NO`
- **Failed Recovery:** `YES`
- **Unrelated Regression Caused:** `NO`
- **Excessive Testing:** `NO`
- **Excessive Retrieval:** `NO`
- **Budget Exhaustion:** `NO`
- **Success After Unnecessary Repetitions:** `NO`

### Diagnostic Notes
- Repeated identical recovery: action 'RETRY_TOOL' executed repeatedly with no state change.
- Recovery without state change: action finished with state_before == state_after.
- Failed recovery: one or more recovery attempts failed to resolve the failure.

## Paired Failure Set Results
Total tasks in failure set: **2**

| Task ID | Baseline | Candidate | Transition | Baseline Action | Candidate Action | Base Lat | Cand Lat | Base Loops | Cand Loops |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `task_s1` | `FAIL` | `FAIL` | `FAIL_TO_STILL_FAILING` | `REPAIR_EDIT` | `RETRY_TOOL` | 0 | 0 | 0 | 0 |
| `task_s2` | `FAIL` | `FAIL` | `FAIL_TO_STILL_FAILING` | `REPAIR_EDIT` | `RETRY_TOOL` | 0 | 0 | 0 | 0 |

## Policy Differences vs. Parent
# Recovery Policy Diff: REC0 vs. REC1

- **Baseline Variant:** `REC0` (hash: `ee77ab01ea32`)
- **Candidate Variant:** `REC1` (hash: `4e8f53a7b9ce`)
- **Identical:** `NO`

## Changed Settings

### Feature Flags & Thresholds
| Setting | Baseline | Candidate |
| :--- | :--- | :--- |
| `early_detection_enabled` | `False` | `True` |
| `no_progress_threshold_turns` | `3` | `1` |

### Retry Budget Bounds
| Bound Parameter | Baseline | Candidate |
| :--- | :--- | :--- |
| `max_alternate_paths` | `1` | `2` |
| `max_same_action_retries` | `2` | `1` |

### Trigger Thresholds
| Trigger Key | Baseline | Candidate |
| :--- | :--- | :--- |
| `bad_edit_max_attempts` | `2` | `1` |
| `early_detection_on_first_error` | `None` | `True` |
| `search_fallback_max_attempts` | `5` | `3` |
| `test_failure_escalate_attempts` | `2` | `1` |

### Action Configurations
| Action Setting | Baseline | Candidate |
| :--- | :--- | :--- |
| `early_diff_inspection` | `None` | `True` |

### Fallback Rules
| Condition | Baseline Rule | Candidate Rule |
| :--- | :--- | :--- |
| `on_bad_edit` | `REPAIR_OR_REVERT` | `IMMEDIATE_REVERT` |
| `on_search_exhaustion` | `EXACT_THEN_TREE_THEN_GRAPH` | `EXACT_THEN_TREE` |
| `on_test_failure` | `CLASSIFY_THEN_INSPECT` | `FAST_INSPECT_STACK` |
| `on_tool_failure` | `RETRY_THEN_ALTERNATE` | `IMMEDIATE_FALLBACK_ALTERNATE` |

### Stop Conditions
- **Added Conditions:** `early_detection_exhausted`

## Unchanged Settings
Total unchanged configuration parameters: **14**

