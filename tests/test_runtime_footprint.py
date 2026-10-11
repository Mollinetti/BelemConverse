"""mvp-1: the backend fits a free-tier machine.

No local-inference, vector-database or deep-learning package may be imported
by the API or declared as a runtime dependency, and the API must report ready
with no language model configured and no model weights on disk.

The import and readiness checks run in subprocesses so they see a fresh
interpreter: earlier tests in the session may already have imported heavy
packages, and the API's startup state is a module-level singleton.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HEAVY_MODULE_PREFIXES = ("chromadb", "torch", "sentence_transformers", "llama_cpp", "langchain")
HEAVY_PACKAGES = {"chromadb", "torch", "sentence-transformers", "llama-cpp-python"}


def _run_python(code: str, *, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _isolated_env(tmp_path: Path) -> dict:
    """Environment with no LLM settings, no model weights, no real data and no network."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("LLM_")}
    empty_models = tmp_path / "models"
    empty_models.mkdir()
    empty_data = tmp_path / "data"
    empty_data.mkdir()
    env.update(
        PYTHONPATH=str(PROJECT_ROOT),
        BELEM_MODELS_DIR=str(empty_models),
        BELEM_DATA_DIR=str(empty_data),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
    )
    return env


def _requirement_name(requirement: str) -> str:
    return re.match(r"[A-Za-z0-9_.-]+", requirement).group(0).lower().replace("_", "-")


def test_api_import_loads_no_heavy_packages(tmp_path):
    code = (
        "import json, sys\n"
        "import api.main\n"
        f"prefixes = {HEAVY_MODULE_PREFIXES!r}\n"
        "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules if m.startswith(prefixes)})))\n"
    )
    result = _run_python(code, cwd=PROJECT_ROOT, env=_isolated_env(tmp_path))

    assert result.returncode == 0, result.stderr[-2000:]
    loaded = json.loads(result.stdout.strip().splitlines()[-1])
    assert loaded == []


def test_dependencies_declare_no_heavy_packages():
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())["project"]
    runtime = {_requirement_name(r) for r in project["dependencies"]}
    extras = {
        name: {_requirement_name(r) for r in reqs}
        for name, reqs in project.get("optional-dependencies", {}).items()
    }

    assert runtime & HEAVY_PACKAGES == set()
    assert not any(name.startswith("langchain") for name in runtime)
    assert "httpx" in runtime
    assert "pandas" not in runtime
    assert "pandas" in extras.get("tools", set())


def test_ready_without_llm(tmp_path):
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    code = (
        "import api.dependencies as deps\n"
        "deps._load_catalog = lambda: [{'placeId': 'p1', 'title': 'Mercado Ver-o-Peso'}]\n"
        "deps.initialize_rag_system()\n"
        "print('READY' if deps.is_system_ready() else 'NOT_READY')\n"
    )
    result = _run_python(code, cwd=workdir, env=_isolated_env(tmp_path))

    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "READY"
