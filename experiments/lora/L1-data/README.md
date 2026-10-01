# L0-TOOL-DISCIPLINE-DATA-v1

This directory contains the dataset curation artifacts and pipeline for **Stage 38** of IMPULSE.

## Structure
- `raw/`: Discovered unprocessed trace dumps.
- `intermediate/`: Filtered, sanitized, and normalized intermediate records.
- `curated/`: Final training partitions:
  - `train.jsonl`: Training examples (disjoint task IDs).
  - `validation.jsonl`: Validation examples for evaluation.
- `fixtures/`: Isolated fixture demonstrations used strictly for pipeline verification (`evidence_mode = FIXTURE`).
- `manifests/`:
  - `dataset_manifest.json`: Machine-readable dataset metadata, hashes, and quality results.
  - `file_manifest.json`: Cryptographic SHA-256 hashes of all files in this directory.
- `reports/`:
  - `stage38_data_report.md`: Detailed empirical audit report.
- `training_contract.json`: Formal contract binding this dataset to Stage 39 PEFT execution.

## Objective
`OBJ-TOOL-DISCIPLINE`: Reduce repeated failing commands, prevent command perseveration without state change, and enforce tool invocation discipline.

## Status
`BLOCKED_BY_DATA` (Pipeline verified; live training trajectories pending external GPU execution).
All fixtures are strictly isolated from the curated partitions. Zero synthetic data in curated partitions.
