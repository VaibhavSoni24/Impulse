# IMPULSE Stage 43: Version Every Candidate Report

**Stage Status:** `STAGE 43 COMPLETE, CANDIDATE VERSIONING VERIFIED`  
**Parent Commit:** `b5d3762c30fe90c6ce2cbb934368c50119eb2a2d`  
**Registered Candidates:** `17`  
**Current Best Candidate:** `M0`  

---

## 1. Stage Status
`STAGE 43 COMPLETE, CANDIDATE VERSIONING VERIFIED`

- Deterministic candidate registry, schema, immutability, and lineage engine established.
- Explicit governance rules enforced: zero new optimization experiments performed, zero adapters created, zero candidates fabricated, and zero historical measurements invented.

## 2. Parent Commit
- **Frozen Parent:** `b5d3762c30fe90c6ce2cbb934368c50119eb2a2d` (Stage 42 final commit).
- **Lineage:** Stage 42 Free Compute Strategy -> Stage 41 Multi-Adapter -> Stage 40 LoRA Ablation -> Stage 39 LoRA Training -> Stage 38 Training Data.

## 3. Candidate Registry
- **Registry Location:** `experiments/candidates/registry.json`
- **History Location:** `experiments/candidates/history.jsonl` (append-only audit log)
- **Current Best Pointer:** `experiments/candidates/current_best.json`
- **Manifest Schema:** `experiments/candidates/schema.json`
- **Total Registered Candidates:** 17

## 4. Historical Candidates Registered
| Candidate ID | Version | Status | Parent | Primary Dimension | Git Commit | Manifest Hash |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `C1` | `1.0.0` | `VALIDATED` | `E2` | `prompt` | `d8f8522f` | `27d4bcfe23e0...` |
| `D1` | `1.0.0` | `VALIDATED` | `E2` | `recovery` | `d8f8522f` | `1e1fcf9c457e...` |
| `E0` | `1.0.0` | `VALIDATED` | `None` | `baseline` | `99c0da32` | `ea693f54934d...` |
| `E1` | `1.0.0` | `VALIDATED` | `E0` | `prompt` | `99c0da32` | `33e9c93b055f...` |
| `E2` | `1.0.0` | `VALIDATED` | `E1` | `state` | `24ea3df3` | `3e4c65c49775...` |
| `L1` | `1.0.0` | `BLOCKED` | `M0` | `adapter` | `4f5c0d8c` | `4363c83bdda8...` |
| `M0` | `1.0.0` | `VALIDATED` | `E0` | `topology` | `d8f8522f` | `3302d97e41cc...` |
| `M1` | `1.0.0` | `VALIDATED` | `M0` | `topology` | `d8f8522f` | `be6f169eaa75...` |
| `M2` | `1.0.0` | `VALIDATED` | `M0` | `topology` | `d8f8522f` | `b25a98cb89cb...` |
| `M3` | `1.0.0` | `VALIDATED` | `M0` | `topology` | `d8f8522f` | `3e916e82eccb...` |
| `M4` | `1.0.0` | `VALIDATED` | `M0` | `topology` | `d8f8522f` | `e736ebafb620...` |
| `M5` | `1.0.0` | `VALIDATED` | `M0` | `topology` | `d8f8522f` | `f8a1f41eac70...` |
| `R1` | `1.0.0` | `VALIDATED` | `E2` | `retrieval` | `24ea3df3` | `6c5da4da85dd...` |
| `R2` | `1.0.0` | `VALIDATED` | `R1` | `retrieval` | `24ea3df3` | `7ca1372163f1...` |
| `RC1` | `0.1.0` | `RESERVED` | `M0` | `packaging` | `4f5c0d8c` | `649283f9ec0f...` |
| `S1` | `1.0.0` | `VALIDATED` | `E2` | `topology` | `d8f8522f` | `40c37cdb79ea...` |
| `V1` | `1.0.0` | `VALIDATED` | `E2` | `topology` | `d8f8522f` | `d687588fffdf...` |

## 5. Candidate Naming Rules
- Canonical vocabulary enforced: `E0` (baseline), `E1` (prompt-v1), `E2` (state-v1), `R1`/`R2` (retrieval), `D1` (recovery), `S1` (scout), `V1` (reviewer), `C1` (context-optimized), `M0`-`M5` (frozen competition candidates), `L1` (LoRA-v1), `RC1` (release candidate).
- Timestamp-only identifiers strictly forbidden. Human-readable canonical names used exclusively.

## 6. Candidate Immutability
- **The Immutability Law:** Once candidate ID X refers to behavior/configuration Y, X MUST NEVER later refer to behavior/configuration Z.
- Behavior or configuration changes strictly require a new candidate identifier.
- Non-behavioral metadata corrections bump patch versions (e.g. `1.0.1`), never mutating finalized manifests in place.

## 7. Lineage
- Every registered candidate records its explicit parent candidate identifier.
- Linear lineage enforced: `E1` -> `E0`, `E2` -> `E1`, `R1` -> `E2`, `R2` -> `R1`, `D1` -> `E2`, `S1` -> `E2`, `V1` -> `E2`, `M0` -> `E0`, `M1-M5` -> `M0`, `L1` -> `M0`, `RC1` -> `M0`.
- Circular parent references strictly rejected.

## 8. Manifest Schema
- Validated by `experiments/candidates/schema.json`.
- Captures all critical dimensions: base model, model revision, root prompt hash, skill hashes, sub-agent hashes, tool contracts, retrieval version, testing version, recovery version, topology, adapter identity, benchmark split hashes, runtime settings, sampling settings, compute environment ID, and evidence mode.

## 9. Comparison System
- **Script:** `scripts/compare_candidates.py`
- Performs deterministic side-by-side comparison between parent and candidate manifests.
- Detects exact changed dimensions, unchanged dimensions, configuration changes, and hash deltas.
- Flags `MULTI_DIMENSION_EXPERIMENT` warnings when more than one major experimental variable changes.

## 10. Run vs Candidate Separation
- A candidate defines the configuration and behavior under test.
- A run represents one execution of that candidate in a specific compute environment.
- Multiple runs aggregate under one candidate without overwriting raw run evidence.

## 11. Promotion Separation
- Lifecycle status (`VALIDATED`, `SMOKE_PASSED`, `CONFIGURED`) kept strictly separate from promotion status (`NOT_PROMOTED`, `PROMOTED`, `REJECTED`).
- A candidate can be experimentally validated without being selected as the current best.

## 12. Current-Best Handling
- **Active Current-Best Candidate:** `M0`
- **Rationale:** M0 is the verified, frozen competition baseline candidate passing full validator and submission packaging checks.
- Strict Rule: Current-best must point to a genuinely validated candidate passing all submission packaging and validator checks. Never set to hypothetical or unverified candidates.

## 13. L1 Special Rule State
- **L1 Candidate Status:** `BLOCKED`
- **L1 Promotion Status:** `BLOCKED`
- **Rationale:** Governed by Section 21. No adapter weights exist, Stage 39 training was blocked by data, and Stage 40 A/B ablation was not executed. L1 is strictly BLOCKED from being marked VALIDATED or PROMOTED.

## 14. RC1 Special Rule State
- **RC1 Candidate Status:** `RESERVED`
- **RC1 Promotion Status:** `RESERVED`
- **Rationale:** Governed by Section 22. RC1 is a release-candidate identity. It remains RESERVED until a validated candidate is formally selected as the competition release candidate in Stage 50.

## 15. Security
- **Zero Secrets Policy:** Candidate manifests are scanned for credentials, API tokens (`ghp_`, `akid`, `kaggle_`, `hf_`), and private keys.
- **Path Normalization:** Local machine paths and usernames stripped and normalized to symbolic/relative references.

## 16. Tests
- **Stage 43 Focused Suite:** `tests/test_candidate_versioning_stage43.py` (26 requirements A through Z).
- **Negative Tests:** Rejection of duplicate registrations, rejection of manifest mutation in place, rejection of invalid status transitions, rejection of unverified promotions, rejection of fake adapter statuses, rejection of leaked credentials.

## 17. Frozen Artifacts
- **Verification:** `local.diff_discipline.frozen_verifier.verify_frozen_artifacts`.
- **Result:** 14/14 MATCH.

## 18. M0-M5 Candidate Packages
- **Validation:** `scripts/validate_submission.py` across candidates M0, M1, M2, M3, M4, M5.
- **Result:** ALL PASSED.

## 19. Known Limitations
- Historical prompt experiments (E1-E11) and retrieval experiments (R1-R4) are registered based on their recorded repository manifests and commit snapshots.
- L1 remains BLOCKED until training data and hardware become available.
- RC1 remains RESERVED until final release evaluation.
