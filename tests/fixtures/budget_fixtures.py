"""Synthetic realistic test fixtures for Tool-Call Budgeting (Stage 26).

DATA CLASSIFICATION: SYNTHETIC / FIXTURE DATA
All fixtures in this module are synthetic and explicitly designed for deterministic unit
and regression testing of tool budgeting, information novelty, waste detection, and caching.
They DO NOT represent live competition traces.
"""

from __future__ import annotations

# 1. Repeated Identical Read Fixture
FIXTURE_READ_PATH = "src/parser.py"
FIXTURE_READ_CONTENT_V1 = "def parse(x): return x.strip()\n"
FIXTURE_READ_CONTENT_V2 = "def parse(x): return x.strip().lower()\n"

# 2. Repeated Directory / Status Output
FIXTURE_STATUS_OUTPUT_1 = "On branch main\nnothing to commit, working tree clean"
FIXTURE_STATUS_OUTPUT_2 = FIXTURE_STATUS_OUTPUT_1

# 3. Semantic Code Search Query & Results
FIXTURE_SEARCH_QUERY = "def parse_query"
FIXTURE_SEARCH_CANDIDATES_1 = ["src/parser.py:10-25", "src/utils.py:40-55"]
FIXTURE_SEARCH_CANDIDATES_2 = ["src/parser.py:10-25", "src/utils.py:40-55"]  # Identical
FIXTURE_SEARCH_CANDIDATES_NEW = ["src/parser.py:10-25", "src/helpers.py:1-20"]  # Partial new

# 4. Graph Query & Results
FIXTURE_GRAPH_SEED = "parse_query"
FIXTURE_GRAPH_SYMBOLS_1 = ["parse_query", "normalize_token", "Tokenizer"]
FIXTURE_GRAPH_RELATIONS_1 = ["calls:normalize_token", "uses:Tokenizer"]
FIXTURE_GRAPH_SYMBOLS_2 = ["parse_query", "normalize_token", "Tokenizer"]  # Unchanged
FIXTURE_GRAPH_SYMBOLS_NEW = ["parse_query", "parse_expression"]  # Partial new

# 5. Test Execution Commands & Outputs
FIXTURE_TEST_CMD = "pytest tests/test_parser.py"
FIXTURE_TEST_EXIT_CODE_FAIL = 1
FIXTURE_TEST_FAILING_TESTS = ["tests/test_parser.py::test_empty"]
FIXTURE_TEST_ERROR_SIG = "AssertionError: None != {}"

FIXTURE_TEST_EXIT_CODE_PASS = 0
FIXTURE_TEST_PASSING_TESTS: list[str] = []
FIXTURE_TEST_PASS_SIG = ""

# 6. Secret Token Candidate for Sanitization
FIXTURE_CMD_WITH_SECRET = "pytest --token=ghp_1234567890abcdef1234567890abcdef1234 tests/test_auth.py"
FIXTURE_PATH_WINDOWS = "src\\core\\parser.py"
FIXTURE_PATH_NORMALIZED = "src/core/parser.py"

# 7. Unrelated Files for Targeted Invalidation
FIXTURE_UNRELATED_PATH = "README.md"
FIXTURE_UNRELATED_CONTENT = "# IMPULSE Autonomous Agent\n"
