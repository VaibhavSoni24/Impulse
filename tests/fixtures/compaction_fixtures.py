"""Synthetic test fixtures for Stage 25 context compaction tests.

DATA CLASSIFICATION: SYNTHETIC / FIXTURE DATA
These fixtures model realistic developer agent observations, including repeated
directory listings, redundant file reads, failing pytest runs with tracebacks,
modified source code, and hypothesis state transitions.
"""

from __future__ import annotations

# 1. Repeated Directory Listing (`ls -la` / tree output)
SYNTHETIC_LS_OUTPUT_RUN_1 = """total 48
drwxr-xr-x 6 runner runner 4096 Sep 28 10:00 .
drwxr-xr-x 4 runner runner 4096 Sep 28 09:50 ..
drwxr-xr-x 2 runner runner 4096 Sep 28 10:01 impulse
drwxr-xr-x 2 runner runner 4096 Sep 28 10:01 tests
-rw-r--r-- 1 runner runner 1024 Sep 28 09:55 pyproject.toml
-rw-r--r-- 1 runner runner 2048 Sep 28 09:55 README.md
"""

# Identical re-run of `ls -la`
SYNTHETIC_LS_OUTPUT_RUN_2 = SYNTHETIC_LS_OUTPUT_RUN_1

# 2. Repeated File Reads
SYNTHETIC_FILE_PATH = "impulse/core/parser.py"
SYNTHETIC_FILE_CONTENT_V1 = """def parse_query(q: str) -> dict:
    if not q:
        raise ValueError("Empty query")
    return {"query": q.strip()}
"""

# Identical read of the same file
SYNTHETIC_FILE_CONTENT_V1_REPEAT = SYNTHETIC_FILE_CONTENT_V1

# Modified version of the file
SYNTHETIC_FILE_CONTENT_V2 = """def parse_query(q: str) -> dict:
    if not q:
        return {}
    return {"query": q.strip().lower()}
"""

# Different file with identical content as V1 (to test no cross-path collapsing)
SYNTHETIC_OTHER_FILE_PATH = "impulse/core/utils.py"
SYNTHETIC_OTHER_FILE_CONTENT = SYNTHETIC_FILE_CONTENT_V1

# 3. Repository Facts
SYNTHETIC_FACT_CATEGORY = "architecture"
SYNTHETIC_FACT_KEY = "test_framework"
SYNTHETIC_FACT_VALUE = "pytest 7.4.0 with asyncio plugin"

# 4. Failing Test with Traceback (Realistic pytest output)
SYNTHETIC_FAILING_TEST_CMD = "pytest tests/test_parser.py -k test_empty_query"
SYNTHETIC_FAILING_TEST_STDOUT = """============================= test session starts ==============================
platform linux -- Python 3.10.12, pytest-7.4.0, pluggy-1.2.0
rootdir: /workspace/repo
plugins: asyncio-0.21.1
collected 5 items / 4 deselected / 1 selected

tests/test_parser.py F                                                   [100%]

=================================== FAILURES ===================================
_______________________________ test_empty_query _______________________________

    def test_empty_query():
>       res = parse_query("")

tests/test_parser.py:14: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

q = ''

    def parse_query(q: str) -> dict:
        if not q:
>           raise ValueError("Empty query")
E           ValueError: Empty query

impulse/core/parser.py:3: ValueError
=========================== short test summary info ============================
FAILED tests/test_parser.py::test_empty_query - ValueError: Empty query
========================= 1 failed, 4 deselected in 0.12s =========================
"""
SYNTHETIC_FAILING_TEST_EXIT_CODE = 1

# 5. Repeated Identical Failing Test Output
SYNTHETIC_FAILING_TEST_STDOUT_REPEAT = SYNTHETIC_FAILING_TEST_STDOUT

# 6. Passing Test Output (After Fix)
SYNTHETIC_PASSING_TEST_CMD = "pytest tests/test_parser.py -k test_empty_query"
SYNTHETIC_PASSING_TEST_STDOUT = """============================= test session starts ==============================
platform linux -- Python 3.10.12, pytest-7.4.0, pluggy-1.2.0
rootdir: /workspace/repo
plugins: asyncio-0.21.1
collected 5 items / 4 deselected / 1 selected

tests/test_parser.py .                                                   [100%]

========================= 1 passed, 4 deselected in 0.08s =========================
"""
SYNTHETIC_PASSING_TEST_EXIT_CODE = 0

# 7. Unittest Runner Failing Output
SYNTHETIC_UNITTEST_FAIL_CMD = "python -m unittest tests/test_parser.py"
SYNTHETIC_UNITTEST_FAIL_STDOUT = """test_valid_query (tests.test_parser.TestParser) ... ok
test_empty_query (tests.test_parser.TestParser) ... FAIL

======================================================================
FAIL: test_empty_query (tests.test_parser.TestParser)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/workspace/repo/tests/test_parser.py", line 22, in test_empty_query
    self.assertEqual(res, {})
AssertionError: None != {}

----------------------------------------------------------------------
Ran 2 tests in 0.005s

FAILED (failures=1)
"""
SYNTHETIC_UNITTEST_FAIL_EXIT_CODE = 1

# 8. Secret Token Leak Candidate (for sanitization testing)
SYNTHETIC_LOG_WITH_SECRET = """Running build with token
Config: API_KEY = "sk-live-abcdef1234567890abcdef123456"
Connecting to server at 127.0.0.1:8080...
Traceback (most recent call last):
  File "server.py", line 10, in connect
    raise ConnectionRefusedError("Could not connect")
ConnectionRefusedError: Could not connect
"""
