"""Entrypoint when invoked as `python -m local.runner`."""

import sys
from local.runner.cli import main

if __name__ == "__main__":
    sys.exit(main())
