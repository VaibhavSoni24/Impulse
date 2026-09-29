# Prompt Baseline Report: `P0`

## Overview
- **Candidate ID:** `P0`
- **Role:** Immutable root prompt baseline for Stage 32 prompt optimization experiments
- **Source Reference:** `experiments\candidates\M0\prompts\root.md`
- **SHA-256 Digest:** `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`
- **Parent Git Commit:** `HEAD`
- **Topology:** `root_only` (M0)
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`

## Quantitative Cost
- **Characters:** 13351
- **Lines:** 108
- **Words:** 1760
- **Estimated Tokens:** 3337

## Immutability Policy
P0 is the frozen reference prompt. It must never be modified in place.
All subsequent prompt candidates (P1, P2, ...) are single-hypothesis deltas derived from P0 or its descendants.
