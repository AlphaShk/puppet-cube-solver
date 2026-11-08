"""Allow ``python -m puppet_edge_picker`` to open the Tk application."""

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
