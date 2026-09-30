### Testing Policy Diff: `T0` (T0) -> `T1` (T1)

- **Parent Policy Hash:** `76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36`
- **Candidate Policy Hash:** `418d055b9cdcdc02923afeee8b8aa57d715c89d45283dfcd8b094fdcaa9dbff1`
- **Identical:** `NO`

#### Enabled Strategy Levels
- `adjacent_enabled`: `False` -> `True`

#### Budgets & Execution Limits
- `max_test_commands`: `2` -> `4`
- `max_test_cases`: `20` -> `40`
- `runtime_budget_seconds`: `120.0` -> `180.0`

#### Escalation Rules
- `escalate_on_targeted_failure`: `False` -> `True`

#### Stopping Rules
- `stop_on_targeted_pass_if_low_risk`: `True` -> `False`
