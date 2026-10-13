"""mvp-2: the slim free-tier image and the committed catalog."""

import subprocess
from pathlib import Path

from belem_converse.catalog import load_places
from belem_converse.cities import get_city_config
from belem_converse.utils.config import BASE_DIR

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog" / "belem.sqlite"


def test_dockerfile_is_slim():
    dockerfile = (ROOT / "Dockerfile").read_text().lower()

    for heavy in ("cmake", "build-essential", "llama"):
        assert heavy not in dockerfile
    assert "copy catalog" in dockerfile
    assert "$port" in dockerfile or "${port" in dockerfile


def test_catalog_is_committed_and_loads():
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "catalog/belem.sqlite"],
        cwd=ROOT, capture_output=True, text=True,
    )

    assert CATALOG.exists()
    assert tracked.returncode == 0, tracked.stderr
    assert len(load_places(CATALOG)) > 1000


def test_city_profile_points_at_the_committed_catalog():
    assert BASE_DIR / get_city_config().catalog_path == CATALOG


def test_committed_reports_hold_no_local_paths():
    for report in ("cleaning_report.json", "osm_report.json"):
        text = (ROOT / "catalog" / report).read_text()
        assert "/Users/" not in text and "/home/" not in text and ":\\\\" not in text


def test_stub_docker_files_are_gone():
    assert not (ROOT / "docker").exists()
    assert not (ROOT / "frontend" / "Dockerfile").exists()


def test_compose_mounts_no_models():
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "models" not in compose
    assert "profiles" not in compose


def test_dockerignore_keeps_secrets_and_raw_data_out():
    ignored = (ROOT / ".dockerignore").read_text().splitlines()

    assert ".env" in ignored
    assert "data/" in ignored
