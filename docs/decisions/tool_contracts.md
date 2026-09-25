# Predefined Tools Reference & Interface Contracts — IMPULSE

This document records the exact parameter signatures, return schemas, budget gating rules, truncation limits, and operational behaviors for the 9 built-in tools defined in `swegemma.tools` (`HARNESS_README.md` Section 6).

---

## 1. Tool Taxonomy & Quick Reference

| Tool Name | Module | Budget-Gated? | Debits Tool Budget? | Mutates State? | Truncation / Limits |
|---|---|:---:|:---:|:---:|---|
| **`run_command`** | `execution.py` | Yes | **Yes** | Yes (in `/workspace`) | 300s timeout; 5,000 chars stdout/stderr |
| **`submit_patch`** | `execution.py` | Yes | **No** (`count_tool_call=False`) | Yes (sets `patch_submitted=True`) | Captures `git diff HEAD`; terminates loop on turn end |
| **`get_status`** | `execution.py` | **No** | **No** (un-gated) | No | Live budget/time query; never fails on budget exhaustion |
| **`read_file`** | `workspace.py` | Yes | **Yes** | No | 1-indexed; dual cap: max 150 lines AND max 10,000 chars |
| **`edit_file`** | `workspace.py` | Yes | **Yes** | Yes | 3-tier matching (exact $\to$ flexible $\to$ regex); diff max 5,000 chars |
| **`write_file`** | `workspace.py` | Yes | **Yes** | Yes | Auto `mkdir -p`; creates or overwrites file |
| **`get_code_neighbors`** | `graph.py` | Yes | **Yes** | No | 4-tier symbol lookup; max 50 neighbors default |
| **`search_similar_code`** | `graph.py` | Yes | **Yes** | No | Top-k cosine similarity over `.npz`; identifier query required |
| **`get_code_subgraph`** | `graph.py` | Yes | **Yes** | No | Extracts induced subgraph of nodes and edges |

---

## 2. Universal Protocol & Response Envelope

All tools return a serialized JSON string.

### Standard Success Envelope
```json
{
  "status": "ok",
  ...
}
```

### Standard Error Envelope
```json
{
  "status": "error",
  "error_type": "<ErrorClass>",
  "error_message": "<Description>",
  "details": { ... }
}
```

### Automatic Budget Warning Warning
When `budget.tool_calls >= 20` and `remaining_tool_calls <= 10`, every tool response automatically includes:
```json
"budget_warning": "Only X tool call(s) remaining (Y/Z used). Finalize your edits and call submit_patch soon."
```

---

## 3. Tool Specifications

### 1. `run_command(command: str) -> str`
- **Purpose:** Executes arbitrary shell commands via `/bin/bash -c` in `/workspace`.
- **Parameters:**
  - `command` (`str`, required): The shell command string to execute.
- **Budget Gating:** Counts against `tool_calls` allowance.
- **Execution Limits:**
  - Timeout: `min(command_timeout_seconds [300s], max(5, int(remaining_time_seconds)))`.
  - Timeout Behavior: Returns `error_type: "TimeoutExceeded"`. **Does NOT terminate the overall agent session** (unless global time budget has expired).
  - Truncation: Both `stdout` and `stderr` are truncated at **5,000 characters** (`max_stdout_chars`).
- **Return Formats:**
  - Success (`exit_code == 0`):
    ```json
    {"status": "ok", "stdout": "...", "exit_code": 0}
    ```
  - Failure (`exit_code != 0`):
    ```json
    {
      "status": "error",
      "error_type": "CommandError",
      "error_message": "Command failed with exit code 1",
      "details": {"stdout": "...", "stderr": "...", "exit_code": 1}
    }
    ```

---

### 2. `submit_patch() -> str`
- **Purpose:** Stages untracked modifications (`git add -N .`), extracts `git diff HEAD` from `/workspace`, records it in `context.submitted_patch`, and sets `context.patch_submitted = True`.
- **Parameters:** None.
- **Budget Gating:** Decorated with `@budget_gated(count_tool_call=False)`.
  - **Does NOT debit the `tool_calls` budget.**
  - Can still be called when `tool_calls_remaining == 0` as long as session wall-clock time remains.
- **Lifecycle Effect:**
  - Once called, the harness waits for the agent to finish its response for the current turn, then immediately terminates the agent loop and initiates Phase 2 verification.
- **Return Format:**
  ```json
  {"status": "ok", "patch_size": 1420, "files_changed": 2}
  ```

---

### 3. `get_status() -> str`
- **Purpose:** Queries active budget consumption, wall-clock elapsed time, and patch submission state.
- **Parameters:** None.
- **Budget Gating:** Completely un-gated (`count_tool_call=False`). Never fails due to budget exhaustion.
- **Return Format (Raw JSON Object):**
  ```json
  {
    "tool_calls_used": 12,
    "patch_submitted": false,
    "patch_size": 0,
    "tool_calls_remaining": 38,
    "max_tool_calls": 50,
    "time_seconds_remaining": 3120.4,
    "max_time_minutes": 60.0,
    "agent_elapsed_seconds": 479.6,
    "max_turns": 500,
    "command_timeout_seconds": 300
  }
  ```

---

### 4. `read_file(filepath: str, start_line: int | None = None, end_line: int | None = None) -> str`
- **Purpose:** Reads file contents from `/workspace` using 1-indexed line numbers.
- **Parameters:**
  - `filepath` (`str`, required): Path relative to `/workspace`. Leading `/` or `/workspace/` stripped automatically.
  - `start_line` (`int | None`, optional): Starting line (1-indexed, inclusive).
  - `end_line` (`int | None`, optional): Ending line (1-indexed, inclusive).
- **Budget Gating:** Debits 1 tool call.
- **Dual Truncation Cap:**
  - Max lines: **150 lines** (`max_file_lines`).
  - Max characters: **10,000 characters** (`max_file_chars`).
  - If truncated, `is_truncated: true` is returned and `end_line` reflects the last line included.
- **Security:** `..` path traversal raises `ValidationError`.
- **Return Format:**
  ```json
  {
    "status": "ok",
    "filepath": "src/module.py",
    "content": "...",
    "start_line": 1,
    "end_line": 150,
    "total_lines": 420,
    "is_truncated": true
  }
  ```

---

### 5. `edit_file(filepath: str, old_string: str, new_string: str, allow_multiple: bool = False) -> str`
- **Purpose:** Replaces occurrences of `old_string` with `new_string` in `/workspace/<filepath>`.
- **Parameters:**
  - `filepath` (`str`, required): File path relative to `/workspace`.
  - `old_string` (`str`, required): Target text to replace.
  - `new_string` (`str`, required): Replacement text.
  - `allow_multiple` (`bool`, default `False`): Must be set to `True` if replacing multiple instances.
- **Budget Gating:** Debits 1 tool call.
- **3-Tier Resilient Replacement Engine (`adk-eval-core`):**
  1. **Exact:** Character-for-character substring match (normalizing `\r\n` $\to$ `\n`).
  2. **Flexible:** Line-by-line match with leading/trailing whitespace stripped; automatically re-indents `new_string` to match original block baseline indentation.
  3. **Regex:** Delimiter tokenization across code punctuation (`( ) : [ ] { } > = <`) joined by `\s*`.
- **Error Behavior:**
  - If `old_string` matches >1 occurrence and `allow_multiple=False`: returns `error_type: "FileEditError"`.
  - If file does not exist, file is 0 bytes, or `old_string` is empty: returns `FileEditError`.
- **Return Format:**
  ```json
  {
    "status": "ok",
    "filepath": "src/module.py",
    "occurrences": 1,
    "strategy": "exact",
    "diff": "--- a/src/module.py\n+++ b/src/module.py\n...",
    "is_truncated": false
  }
  ```

---

### 6. `write_file(filepath: str, content: str) -> str`
- **Purpose:** Creates or completely overwrites a file at `/workspace/<filepath>`, automatically creating parent directories (`mkdir -p`).
- **Parameters:**
  - `filepath` (`str`, required): Path relative to `/workspace`.
  - `content` (`str`, required): Complete file content string.
- **Budget Gating:** Debits 1 tool call.
- **Return Format:**
  ```json
  {"status": "ok", "filepath": "tests/repro.py", "size": 342}
  ```

---

### 7. `get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str`
- **Purpose:** Traverses the pre-computed NetworkX call/dependency graph (`data/graphs/<repo>.json`) for AST relationships.
- **Parameters:**
  - `node` (`str`, required): Symbol identifier (e.g., `"FastAPI.get"`, `"Request"`).
  - `edge_type` (`str | None`, optional): Edge filter (e.g., `"CALLS"`, `"DEFINED_IN"`, `"IMPORTS"`).
  - `max_neighbors` (`int`, default `50`): Maximum neighbors to return.
- **Symbol Resolution:** 4-tier resolver: exact match $\to$ suffix match (`.` or `/`) $\to$ case-insensitive $\to$ substring.
- **Budget Gating:** Debits 1 tool call.
- **Return Format:**
  ```json
  {"status": "ok", "node": "fastapi.applications.FastAPI", "neighbors": ["..."], "count": 18}
  ```

---

### 8. `search_similar_code(query: str, k: int = 10) -> str`
- **Purpose:** Computes cosine similarity between `query` and pre-computed symbol embeddings (`data/embeddings/<repo>.npz`).
- **Parameters:**
  - `query` (`str`, required): Class, function, or symbol name.
  - `k` (`int`, default `10`): Number of nearest neighbors to return.
- **Offline Resolution Note:** Queries must be symbol or identifier names (e.g., `"HTTPConnection"` or `"parse_header"`), not conversational natural language sentences, because the sandbox runs offline without a live embedding neural network.
- **Budget Gating:** Debits 1 tool call.
- **Return Format:**
  ```json
  {
    "status": "ok",
    "query": "HTTPConnection",
    "results": [{"node_name": "...", "code": "...", "similarity": 0.9412}],
    "count": 10
  }
  ```

---

### 9. `get_code_subgraph(nodes: list[str]) -> str`
- **Purpose:** Extracts the induced subgraph (nodes and interconnecting edges) for a list of symbols.
- **Parameters:**
  - `nodes` (`list[str]`, required): List of node symbol names.
- **Budget Gating:** Debits 1 tool call.
- **Return Format:**
  ```json
  {
    "status": "ok",
    "nodes": ["node_a", "node_b"],
    "edges": [{"from": "node_a", "to": "node_b", "type": "CALLS"}],
    "node_count": 2,
    "edge_count": 1
  }
  ```
