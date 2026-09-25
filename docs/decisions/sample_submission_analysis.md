# Sample Submission Architectural Analysis — IMPULSE

This document analyzes the official starter kit sample submission (`data/competition/sample_submission/`) provided by Google DeepMind and Kaggle for the **Gemma 4 Developer Agent Competition**.

---

## 1. Directory Tree & Layout

```text
sample_submission/
├── agent.yaml                       # Root agent configuration (entrypoint)
├── eval_config.yaml                 # Participant evaluation budget overrides
├── configs/
│   └── sampling.yaml                # Generation parameters (loaded via !include)
├── prompts/
│   ├── system.md                    # Root agent system prompt (loaded via !include)
│   └── analyzer.md                  # Sub-agent system prompt (loaded via !include)
├── sub_agents/
│   └── code_analyzer.yaml           # Specialized read-only delegate agent
└── adapters/                        # PEFT LoRA adapters (.safetensors)
    ├── main_lora/
    │   ├── adapter_config.json      # Rank 4 LoRA configuration
    │   └── adapter_model.safetensors # LoRA weight tensors (217 KB)
    └── tool_lora/
        ├── adapter_config.json      # Rank 4 LoRA configuration
        └── adapter_model.safetensors # LoRA weight tensors (217 KB)
```

---

## 2. Component Analysis & Schema Semantics

### 2.1. Root Agent Configuration (`agent.yaml`)

```yaml
name: swe_baseline_agent
model: gemma-4-31b-it-qat-w4a16-ct
adapter: main_lora
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
  - agent_tool:
      config_path: sub_agents/code_analyzer.yaml
      skip_summarization: true
generate_content_config: !include configs/sampling.yaml
```

**Key Architectural Rules:**
1. **Root Discovery:** Exactly one root config (`agent.yaml`, `agent.yml`, `root_agent.yaml`, or `root_agent.yml`) must reside in the archive root. Zero or multiple root configs raise validation errors.
2. **Model Declaration:** Must declare `gemma-4-31b-it-qat-w4a16-ct`.
3. **Adapter Binding:** `adapter: main_lora` binds to `adapters/main_lora/`. It is optional (`null` allowed if no adapter is used).
4. **Tool Declarations:** Predefined tools are referenced by string name from the 9 built-in tools.
5. **AgentTool Delegation:** Sub-agents can be wrapped as tools (`agent_tool:`). `skip_summarization: true` returns the sub-agent's direct output to the parent context without invoking an intermediate summarization LLM call.

### 2.2. Specialized Sub-Agent (`sub_agents/code_analyzer.yaml`)

```yaml
name: code_analyzer_agent
description: Analyzes repository source files and symbol graphs to locate root causes.
model: gemma-4-31b-it-qat-w4a16-ct
adapter: tool_lora
instruction: !include ../prompts/analyzer.md
tools:
  - read_file
  - search_similar_code
  - get_code_neighbors
  - get_code_subgraph
generate_content_config: !include ../configs/sampling.yaml
```

**Key Architectural Rules:**
1. **Description Requirement:** The `description` field is mandatory for sub-agents; the parent LLM reads this description to decide when to delegate a query.
2. **Single Base Model Enforcement:** Sub-agents MUST declare the exact same base model (`gemma-4-31b-it-qat-w4a16-ct`). Declaring another model variant raises `ParticipantVisibleError`.
3. **Independent LoRA Routing:** Sub-agents can use a completely different adapter (`adapter: tool_lora`). The vLLM server automatically routes requests to the correct adapter endpoint.
4. **Tool Scoping:** Sub-agents can be restricted to read-only tools (`read_file`, `search_similar_code`, etc.), preventing accidental filesystem edits during exploration.

### 2.3. The Sandboxed `!include` Directive

- **Text Files (`.md`, `.txt`):** Injected as raw UTF-8 string literals into the parent YAML field (e.g., `instruction: !include prompts/system.md`).
- **YAML Files (`.yaml`, `.yml`):** Injected as parsed nested dictionaries/lists (e.g., `generate_content_config: !include configs/sampling.yaml`).
- **Relative Path Resolution:**
  - Resolved relative to the directory containing the file with the `!include` tag.
  - In `agent.yaml`, `prompts/system.md` resolves to `<root>/prompts/system.md`.
  - In `sub_agents/code_analyzer.yaml`, `../prompts/analyzer.md` resolves to `<root>/prompts/analyzer.md`.
- **Security Sandboxing:** Paths containing absolute directories, `..` escaping above the submission root, null bytes, or external symlinks raise `PathTraversalError`. Maximum include recursion depth is 10.

### 2.4. Generation Configuration (`configs/sampling.yaml`)

```yaml
temperature: 0.2
top_p: 0.95
max_output_tokens: 16384
thinking_config:
  thinking_level: high
  thinking_budget: 4096
  include_thoughts: true
```

- `max_output_tokens`: Bounded between 1 and 32,768 (default 16,384).
- `thinking_config.thinking_budget`: Bounded between 1 and 32,768 (default 4,096).
- `thinking_config.thinking_level`: Case-insensitive (`"MINIMAL"`, `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"NONE"`).
- `thinking_config.include_thoughts`: Boolean controlling whether thought chains are preserved in context.
- **Strictly Prohibited Fields:**
  Setting `tools`, `system_instruction`, `http_options`, `safety_settings`, or `response_schema` inside `generate_content_config` triggers an immediate validation failure.

### 2.5. Participant Evaluation Configuration (`eval_config.yaml`)

```yaml
evaluation:
  timeout_seconds: 60
  max_tool_calls: 10
  max_time_minutes: 1
  max_turns: 50
```

- Allows the competitor to voluntarily constrain per-task execution limits during evaluation.
- Overrides global defaults (`max_time_minutes: 60.0`, `command_timeout_seconds: 300`, `max_turns: 500`).

---

## 3. Implications for IMPULSE Architecture

1. **Alignment with Frozen Architecture:**
   IMPULSE's planned architecture in `IMPULSE.md` (root orchestrator delegating to specialized read-only analysis tools with independent prompts) directly mirrors the pattern demonstrated in the sample submission.
2. **Context Window Isolation:**
   Using `agent_tool` with `skip_summarization: true` allows exploratory file reading and graph searches to occur in sub-agent sessions without filling the root agent's primary 32k context window.
3. **Adapter Strategy:**
   Because different agents can reference different adapters under `adapters/<name>/`, IMPULSE can deploy specialized LoRA fine-tunes for code generation vs. issue localization within the single `< 3 GiB` submission budget.
