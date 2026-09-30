# Recovery Optimization Experiment Report: Candidate `REC2`

## Candidate Metadata
- **Candidate ID:** `REC2`
- **Parent Candidate:** `REC0`
- **Policy Hash:** `12182d63be0a0211468cb05a0b387d3401a02831cc9c8c31d0859b8cff20c519`
- **Evidence Mode:** `UNAVAILABLE`
- **Benchmark Split:** `dev`
- **Promotion Decision:** `NO_ACTIONABLE_DATA`
- **Decision Rationale:** Candidate initialized in UNAVAILABLE evidence mode (local hardware limitation).

## Invariance Verification
- **Root Prompt Hash:** `2360d4bf64dd...` (Invariant)
- **Retrieval Policy Hash:** `3e1b234a2ac7...` (Invariant R0)
- **Testing Policy Hash:** `76820d5c5e2a...` (Invariant T0)
- **Topology:** `root_only` (Invariant)
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct` (Invariant)
- **Test Strategy Skill:** `3d027b0f9a7f...` (Frozen)
- **Repo Triage Skill:** `ac7a967136bb...` (Frozen)

## Causal Recovery Hypothesis
- **Target Failure:** `FAILED_RECOVERY / RETRY_WASTE`
- **Observation:** Repeated same-action retries fail to alter repository state.
- **Hypothesis:** Routing immediately to an alternate recovery tool/path avoids wasted retries.
- **Recovery Change:** Route to alternate tool/search on primary action failure instead of repeating.
- **Expected Signal:** retry_count decreases; alternate_path_success_rate increases.
- **Rejection Condition:** New recovery loops or collateral regressions.

## Recovery Quality & Effectiveness
| Metric | Value |
| :--- | :--- |
| Targeted Recovery Success Rate | 0.0% |
| Targeted Failure Reduction | 0 tasks |
| Recovery Loop Count | 0 |
| Detection Latency (Events) | 0.0 |
| Detection Latency (Turns) | 0.0 |
| Average Recovery Attempts | 0.00 |
| Tasks Recovered After Failure | 0 |
| Tasks Abandoned After Failure | 0 |
| Alternate Path Success Rate | 0.0% |
| First-Attempt Success Rate | 0.0% |

## Resource & Recovery Cost Metrics
| Metric | Value |
| :--- | :--- |
| Total Recovery Tool Calls | 0 |
| Recovery Turns Used | 0 |
| Total Retries Executed | 0 |
| Total Recovery Runtime | 0.0 ms |
| Additional Tests Caused | 0 |
| Additional Retrievals Caused | 0 |
| Additional Context Growth | 0 bytes |
| Repeated Failed Interventions | 0 |

## Deterministic Diagnostics
- **Late Recovery:** `NO`
- **Repeated Identical Recovery:** `NO`
- **Recovery Oscillation:** `NO`
- **Retry Waste:** `NO`
- **Recovery Without State Change:** `NO`
- **Missed Recovery Opportunity:** `NO`
- **Failed Recovery:** `NO`
- **Unrelated Regression Caused:** `NO`
- **Excessive Testing:** `NO`
- **Excessive Retrieval:** `NO`
- **Budget Exhaustion:** `NO`
- **Success After Unnecessary Repetitions:** `NO`

## Policy Differences vs. Parent
# Recovery Policy Diff: REC0 vs. REC2

- **Baseline Variant:** `REC0` (hash: `ee77ab01ea32`)
- **Candidate Variant:** `REC2` (hash: `12182d63be0a`)
- **Identical:** `NO`

## Changed Settings

### Feature Flags & Thresholds
| Setting | Baseline | Candidate |
| :--- | :--- | :--- |
| `alternate_path_routing_enabled` | `False` | `True` |
| `early_detection_enabled` | `False` | `True` |
| `no_progress_threshold_turns` | `3` | `1` |

### Retry Budget Bounds
| Bound Parameter | Baseline | Candidate |
| :--- | :--- | :--- |
| `max_alternate_paths` | `1` | `3` |
| `max_same_action_retries` | `2` | `1` |

### Trigger Thresholds
| Trigger Key | Baseline | Candidate |
| :--- | :--- | :--- |
| `alternate_path_on_failure` | `None` | `True` |
| `bad_edit_max_attempts` | `2` | `1` |
| `search_fallback_max_attempts` | `5` | `3` |
| `test_failure_escalate_attempts` | `2` | `1` |

### Action Configurations
| Action Setting | Baseline | Candidate |
| :--- | :--- | :--- |
| `route_alternate_investigation` | `None` | `True` |

### Fallback Rules
| Condition | Baseline Rule | Candidate Rule |
| :--- | :--- | :--- |
| `on_bad_edit` | `REPAIR_OR_REVERT` | `REVERT_AND_ALTERNATE_APPROACH` |
| `on_search_exhaustion` | `EXACT_THEN_TREE_THEN_GRAPH` | `TREE_THEN_GRAPH_ROUTE` |
| `on_test_failure` | `CLASSIFY_THEN_INSPECT` | `REVISE_HYPOTHESIS_ALTERNATE_PATH` |
| `on_tool_failure` | `RETRY_THEN_ALTERNATE` | `ALTERNATE_TOOL_ROUTE` |

### Stop Conditions
- **Added Conditions:** `no_alternate_path_available`

## Unchanged Settings
Total unchanged configuration parameters: **13**

