"""`python -m bpreflight` 入口（与 `bpreflight` console script 等价）。"""

import sys

from bpreflight.cli import main

if __name__ == "__main__":
    sys.exit(main())
