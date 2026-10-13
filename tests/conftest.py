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


# --- mvp-2 API fixtures --------------------------------------------------------

LLM_VARS = [
    "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY",
    "LLM_FALLBACK_BASE_URL", "LLM_FALLBACK_MODEL", "LLM_FALLBACK_API_KEY",
]


@pytest.fixture
def client(built_catalog, monkeypatch):
    """A TestClient over the fixture catalog, with no model configured."""
    from fastapi.testclient import TestClient

    import api.dependencies as deps
    import api.routes as routes
    from api.main import app
    from belem_converse.catalog import load_places

    for name in LLM_VARS:
        monkeypatch.delenv(name, raising=False)
    # Startup state and the lazily built retriever are module-level singletons.
    monkeypatch.setattr(deps, "_catalog", None)
    monkeypatch.setattr(deps, "_load_catalog", lambda: load_places(built_catalog))
    for attr in ("_place_cache", "_category_matcher", "_ranking_engine", "_retriever"):
        monkeypatch.setattr(routes, attr, None)
    with TestClient(app) as test_client:
        yield test_client


def fake_model(monkeypatch, **behaviour):
    """Replace ``llm.summarize`` with an AsyncMock; returns the mock."""
    from unittest.mock import AsyncMock

    from belem_converse import llm

    mock = AsyncMock(**behaviour)
    monkeypatch.setattr(llm, "summarize", mock)
    return mock
