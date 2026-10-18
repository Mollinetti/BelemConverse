"""mvp-2: every setting the code reads is documented in .env.example."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READ = re.compile(
    r"""(?:getenv|environ\.get|environ\[|_number_setting)\(?\s*["']([A-Z][A-Z0-9_]*)["']"""
)
ENV_CONSTANT = re.compile(r"""_ENV_VAR\s*=\s*["']([A-Z][A-Z0-9_]*)["']""")
# llm.py reads f"{prefix}BASE_URL" etc. for its two providers.
PREFIXED = re.compile(r"""f["']\{prefix\}([A-Z][A-Z0-9_]*)["']""")
LLM_PREFIXES = ("LLM_", "LLM_FALLBACK_")


def documented() -> set[str]:
    text = (ROOT / ".env.example").read_text()
    return set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]*)=", text, re.MULTILINE))


def read_by_code() -> set[str]:
    names = set()
    for path in [*(ROOT / "api").rglob("*.py"), *(ROOT / "belem_converse").rglob("*.py")]:
        source = path.read_text()
        names |= set(READ.findall(source)) | set(ENV_CONSTANT.findall(source))
        names |= {p + s for s in PREFIXED.findall(source) for p in LLM_PREFIXES}
    return names


def render_env_keys() -> set[str]:
    return set(re.findall(r"^\s*-\s*key:\s*([A-Z][A-Z0-9_]*)", (ROOT / "render.yaml").read_text(),
                          re.MULTILINE))


def test_grep_finds_the_known_settings():
    assert {"LLM_BASE_URL", "LLM_FALLBACK_API_KEY", "LLM_TIMEOUT_S", "BELEM_DATA_DIR",
            "BELEMCONVERSE_CITY", "LLM_DAILY_CAP", "ALLOWED_ORIGINS"} <= read_by_code()


def test_every_setting_read_by_code_is_documented():
    assert read_by_code() - documented() == set()


def test_every_render_setting_is_documented():
    keys = render_env_keys()

    assert "LLM_API_KEY" in keys
    assert keys - documented() == set()
