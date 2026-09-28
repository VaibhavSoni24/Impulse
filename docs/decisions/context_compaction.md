# Architecture Decision Record: Safe Context Compaction (Stage 25)

## Status
ACCEPTED (Stage 25 Implementation)

## Context
During iterative issue reproduction, localization, code modification, and regression testing, autonomous agents generate large volumes of observations:
- Repeated directory listings (`ls`, `find`, tree outputs);
- Redundant full-file dumps from repeated `read_file` calls on unchanged source files;
- Verbose test execution logs containing hundreds of passing test cases and framework boilerplate surrounding a small set of failure diagnostics;
- Repeated architectural and repository facts;
- Evolving root-cause hypotheses and speculative investigation markers.

Without principled context management, agent contexts experience bloat, consuming unnecessary context window space and degrading model reasoning focus. However, aggressive or lossy summarization poses fatal risks to autonomous software engineering:
1. Summarizing away exact line numbers, file paths, or exception messages prevents precise fault localization.
2. Slicing test outputs with naive first-N / last-N head/tail truncation frequently drops the exact assertion failure or traceback frame needed for debugging.
3. Using an LLM to generate free-form summaries can hallucinate, omit subtle syntax errors, or obscure root causes.
4. Overwriting or deleting past hypotheses hides contradictory evidence and disrupts no-progress detection.

PLAN.md Stage 25 mandates deterministic, loss-bounded Context Compaction that enforces strict information-preservation guarantees.

---

## Decision

### 1. Architectural Principles
- **Deterministic and Loss-Bounded:** Prefer exact content hashing, structured metadata, and deterministic rule-based compaction over opaque LLM-generated summaries.
- **Explicit Preservation Invariants:** Every compaction operation must be classifiable by an explicit safety policy layer. When uncertain, the system MUST preserve evidence exactly.
- **Authoritative Continuity:** Integration with `TaskState`, `FailureClassifierV1` (E9), `NoProgressDetectorV1` (E10), and `RecoveryControllerV1` (E11) preserves full causal signals, repetition tracking, and recovery decisions without semantic degradation.

### 2. Subsystem Structure
The subsystem is encapsulated within `local/context_compaction/`:

| Module | Core Responsibility | Key Invariants |
|---|---|---|
| `models.py` | Data models and enums | Defines `CompactionAction`, `ObservationType`, `HypothesisStatus`, and typed observation/log records. |
| `fingerprints.py` | SHA-256 fingerprinting & sanitization | Content-based SHA-256 hashing; distinct paths with identical content are never conflated; secret scrubbing. |
| `file_tracking.py` | `ChangedFileTracker` | Tracks initial and latest fingerprints, edit counts, change status, and relevance without silently dropping unchanged files. |
| `log_compaction.py` | `compact_test_log` | Deterministically preserves commands, exit codes, runners, failing tests, error lines, tracebacks, and file:line refs while collapsing boilerplate. |
| `repo_cache.py` | `RepositoryMapCache` | Caches high-level repo layout and conventions keyed by deterministic manifest digest; invalidates immediately upon source modification. |
| `observation_summary.py` | Deduplication & lifecycle tracking | Tracks repeated facts with observation counters, maintains hypothesis transitions without erasing evidence, deduplicates identical observations. |
| `policy.py` | `CompactionPolicy` | Explicit safety rules: classifies into `SAFE_TO_COMPACT`, `PRESERVE_EXACTLY`, `PRESERVE_WITH_STRUCTURE`, defaulting to `PRESERVE`. |
| `adapter.py` | `CompactedTaskContext` | Adapter coordinating compaction with `TaskState` and bridging to `FailureClassificationContext` and `CycleSnapshot`. |

### 3. Hard Safety and Information-Preservation Invariants
The system strictly forbids summarizing or truncating away:
- Critical error lines (`AssertionError`, syntax errors, exceptions);
- Exact code fragments and traceback stack frames (`File "...", line X, in ...`);
- Exit codes and command invocations required to interpret results;
- Failing test names and status (`PASS`/`FAIL`/`ERROR`/`TIMEOUT`);
- File paths and line references required for causal localization;
- Exact diff content currently under review;
- Security-sensitive findings.

Items safe to compact:
- Identical re-reads of unchanged files (references existing fingerprint and observation count);
- Repeated identical directory listings (`ls -la`);
- Duplicate repository facts (tracked via observation counters);
- Test runner boilerplate banners, progress bars, and repeated passing test noise (`ok`, `PASSED`).

### 4. Repository-Map Cache Invalidation Protocol
`RepositoryMapCache` stores structural repository facts (framework, top-level layout, test directories, conventions) keyed strictly by `manifest_digest` (SHA-256 digest of tracked files and their latest content fingerprints).
- When any tracked file is edited or added, the manifest digest shifts.
- Any subsequent cache query for the new digest results in a clean cache miss (`None`), ensuring stale source maps are never served to the agent.
- Explicit invalidation is supported via `invalidate()`.

### 5. Empirical Grounding & Trace Availability
- **Live Competition Traces:** Real competition-scale execution traces using `gemma-4-31b-it-qat-w4a16-ct` are **UNAVAILABLE** on the local development host due to hardware constraints (requires 4x L4 GPUs; local runs recorded `execution_unavailable_local_host`).
- **Empirical Evidence:** All validation is grounded in deterministic synthetic test fixtures (`tests/fixtures/compaction_fixtures.py`) and focused regression suites.
- **Zero Fabrication:** No token reduction percentages, solve rate improvements, or benchmark scores are fabricated or claimed.

---

## Consequences
- Bounded, predictable context size across extended multi-turn tasks.
- Complete diagnostic safety: no failure signals or stack frames are lost during compaction.
- Seamless compatibility with frozen E9 failure classification, E10 no-progress detection, E11 recovery paths, and Stage 24 multi-agent topology packages.
- Zero scope creep: adaptive budgeting (Stage 26), automated cleanup (Stage 27), clean-copy evaluation (Stage 28), and fine-tuning (Stage 29) are strictly deferred.
