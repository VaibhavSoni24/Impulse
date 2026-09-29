# Benchmark Dataset Splits Audit Report (Stage 29)

- **Audit Status:** PASS
- **Policy Name:** `repo_disjoint` (Version 1.0.0)
- **Manifest SHA-256:** `ddbd2baab4567cba`
- **Source Dataset:** `data/competition/tasks.jsonl`
- **Source Records:** 129
- **Source SHA-256:** `e4b3fd60f69dbc2b`
- **Git Commit:** `899e62395066787b0ec09c4069aae94b8744da71`
- **Generated At:** 2026-09-29T05:47:50.514499+00:00

## 1. Split Allocation Summary

| Split | Task Count | Proportion | Repositories | Task Set SHA-256 | File SHA-256 |
|---|---|---|---|---|---|
| **DEV** | 67 | 51.94% | `fastapi/fastapi` (67) | `ca1344dd8abd` | `1b95c9fcfad8` |
| **VALIDATION** | 48 | 37.21% | `Textualize/rich` (48) | `2aaf4ebb5fec` | `32a26959af62` |
| **HELD_OUT** | 14 | 10.85% | `encode/httpx` (1), `psf/requests` (13) | `3d2db96fe3a3` | `8dae6b4c276b` |

## 2. Leakage and Isolation Verification

| Audit Check | Status | Details |
|---|---|---|
| Internal Uniqueness | PASS | Task IDs unique within each split |
| Cross-Split Task Disjointness | PASS | Overlap: 0 tasks |
| No Duplicate Text Across Splits | PASS | Overlap: 0 descriptions |
| Repository Isolation | PASS | Policy: `repo_disjoint` |
| Commit Snapshot Isolation | PASS | Zero tasks sharing a base commit cross splits |
| Source Fidelity | PASS | Content verified against source |
| Accounting Completeness | PASS | Total accounted: 129 |

## 3. Exclusions

Zero records excluded. 100% of source dataset validly partitioned.
