"""Main executable entrypoint for python -m releasepilot."""

import sys
from releasepilot.cli import main

if __name__ == "__main__":
    sys.exit(main())
