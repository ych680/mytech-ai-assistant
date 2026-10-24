"""Read-only v2.1 TEST consistency checker; never generates or repairs files."""

import sys

try:
    from .sync_catalogue import main
except ImportError:
    from sync_catalogue import main


if __name__ == "__main__":
    sys.exit(main([*sys.argv[1:], "--check"]))
