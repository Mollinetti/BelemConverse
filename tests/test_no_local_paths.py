"""mvp-3 K07: no tracked Python writes to a hardcoded local path such as a debug.log."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL_HOME = "/Use" + "rs/"  # spelled in two parts so this file does not match itself
# test_deploy_files.py asserts the absence of this prefix in the committed reports.
ASSERTS_ABSENCE = {"tests/test_deploy_files.py"}


def test_no_tracked_python_file_names_a_local_home_path():
    files = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()

    offenders = [
        f for f in files
        if f not in ASSERTS_ABSENCE and LOCAL_HOME in (ROOT / f).read_text(errors="ignore")
    ]

    assert offenders == []
