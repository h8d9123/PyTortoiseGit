"""版本标记：__version__ 与 pyproject.toml / requirements 头保持一致。"""

import re
from pathlib import Path

import pytortoisegit

ROOT = Path(__file__).resolve().parent.parent


def test_version_matches_pyproject():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert m, "pyproject.toml 缺少 version"
    assert pytortoisegit.__version__ == m.group(1)


def test_requirements_marked_with_version():
    for rel in ("requirements.txt", "requirements-dev.txt"):
        head = (ROOT / rel).read_text(encoding="utf-8").splitlines()[0]
        assert pytortoisegit.__version__ in head, rel


def test_requirements_pins_pyside6():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert re.search(r"^PySide6==\d", text, re.M)
