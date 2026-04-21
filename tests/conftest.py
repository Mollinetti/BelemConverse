"""Pytest config.

Ensures the project root is on ``sys.path`` so the tests can resolve
``belem_converse`` even when the package has not been ``pip install -e .``-d
yet (handy for CI / contributor first-runs).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
