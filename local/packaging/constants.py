"""Package validation subsystem constants and competition constraints.

Authoritative source: HARNESS_README.md Section 2 & Section 3,
swegemma configuration limits (swegemma/config.py), and competition rules.
"""

from __future__ import annotations

import re

# Validator and Rule-set Metadata
VALIDATOR_VERSION = "1.0.0"
RULESET_VERSION = "2026.1"
COMPETITION_RULES_SOURCE = "https://www.kaggle.com/competitions/gemma-4-developer-agent/overview"
COMPETITION_RULES_VERIFIED_DATE = "2026-10-23"

# Authoritative competition limits from swegemma
MAX_TOTAL_SIZE_BYTES = 3_221_225_472  # 3 GiB unpacked
MAX_FILE_COUNT = 10_000
MAX_YAML_FILES = 1_000
MAX_YAML_SIZE_BYTES = 52_428_800  # 50 MiB
MAX_SKILL_SIZE_BYTES = 52_428_800  # 50 MiB
MAX_INSTRUCTION_CHARS = 1_000_000
MAX_AGENTS = 500
MAX_SUB_AGENT_DEPTH = 50
MAX_LOOP_ITERATIONS = 500
MAX_INCLUDE_DEPTH = 10

# LoRA / PEFT Constraints (vLLM serving limits)
MAX_LORA_RANK = 128
MAX_LORAS = 8

# Generation Constraints (4x L4 GPU context limit)
MAX_OUTPUT_TOKENS_LIMIT = 32_768
MAX_THINKING_BUDGET_LIMIT = 32_768
VALID_THINKING_LEVELS = {"minimal", "low", "medium", "high", "none"}

# Compression ratio ceiling for zip-bomb protection (for files > 1 MB)
SUSPICIOUS_COMPRESSION_RATIO_THRESHOLD = 100.0
COMPRESSION_RATIO_MIN_UNCOMPRESSED_SIZE = 1_048_576  # 1 MiB

# Allowed file extensions within submission package
ALLOWED_FILE_EXTENSIONS = {
    ".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"
}

# Permitted base models from ModelRegistry
PRIMARY_BASE_MODEL = "gemma-4-31b-it-qat-w4a16-ct"
ALLOWED_MODELS = {
    "gemma-4-31b-it-qat-w4a16-ct",
    "gemma-4-31b-it",
    "gemma-4-31b",
    "gemma-4-27b-it",
    "gemma-4-27b",
    "gemma-4-26b-a4b-it",
    "gemma-4-26b-a4b",
    "diffusiongemma-26b-a4b-it",
    "gemma-4-12b-it",
    "gemma-4-12b",
    "gemma-4-9b-it",
    "gemma-4-9b",
    "gemma-4-e4b-it",
    "gemma-4-e4b",
    "gemma-4-e2b-it",
    "gemma-4-e2b",
}

# The 9 predefined SWE-bench tools from ToolRegistry
PREDEFINED_TOOLS = {
    "run_command",
    "submit_patch",
    "get_status",
    "read_file",
    "edit_file",
    "write_file",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
}

# Prohibited fields in generate_content_config that bypass sandbox
PROHIBITED_GENERATE_CONTENT_CONFIG_FIELDS = {
    "tools",
    "system_instruction",
    "http_options",
    "safety_settings",
    "response_schema",
}

# Prohibited binary/pickle weight extensions
PROHIBITED_WEIGHT_EXTENSIONS = {
    ".bin", ".pt", ".pth", ".pkl", ".pickle", ".ckpt", ".h5", ".onnx"
}

# Prohibited development-only or temporary directory/file names
PROHIBITED_DEV_DIRECTORIES = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".coverage",
    "node_modules",
    ".idea",
    ".vscode",
    ".agents",
    "benchmark",
    "experiments",
    "scratch",
    "tmp",
    "temp",
}

PROHIBITED_DEV_FILES = {
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".DS_Store",
    "Thumbs.db",
    "tasks.jsonl",
    "held_out.lock",
    "PLAN.md",
    "IMPULSE.md",
    "AGENTS.md",
}

# Secret detection patterns (regexes)
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("GitHub Personal Access Token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Hugging Face Token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("Kaggle API Key", re.compile(r"\bkaggle_[A-Za-z0-9]{16,}\b")),
    ("Private Key Header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Hardcoded API Key Pattern", re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]")),
    ("Hardcoded Password Pattern", re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]{6,}['\"]")),
]

# Host machine specific absolute path pattern
HOST_PATH_PATTERN = re.compile(
    r"(?:(?:[a-zA-Z]:[/\\]+|/(?:home|root|Users)/)[a-zA-Z0-9._-]+(?:[/\\]+[a-zA-Z0-9._-]+)*)",
    re.IGNORECASE,
)
