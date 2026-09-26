"""Package entrypoint for python -m local.evaluation."""

from __future__ import annotations

import sys
from local.evaluation.cli import main

if __name__ == "__main__":
    sys.exit(main())
