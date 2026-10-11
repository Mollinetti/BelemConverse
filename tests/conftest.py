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


# --- mvp-1 catalog fixtures --------------------------------------------------

import shutil  # noqa: E402

import pytest  # noqa: E402

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture
def built_catalog(tmp_path):
    """Run the catalog build on the hand-written fixtures; yield the SQLite path.

    The build also writes ``cleaning_report.json`` next to the database.
    """
    from belem_converse.tools.build_catalog import build

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    shutil.copy(FIXTURES_DIR / "raw_repair_sample.csv", raw_dir)
    out_dir = tmp_path / "belem"
    build(csv_path=FIXTURES_DIR / "catalog_raw_sample.csv", raw_dir=raw_dir, out_dir=out_dir)
    return out_dir / "places.sqlite"
