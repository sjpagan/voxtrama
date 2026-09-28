"""Published text uses only what a keyboard types.

Em and en dashes, curly quotes, the ellipsis character and non-breaking
spaces read as text that went through a word processor or a model, and
they show up in diffs as characters nobody can type back. The README, the
guide, the interface strings and the comments all stay with the plain
ones: a full stop or a comma instead of a dash, straight quotes, three
dots.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"[\u2010-\u2015\u2018\u2019\u201c\u201d\u2026\u00a0]")
ROOTS = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "NOTICE",
    ".env.example",
    "Dockerfile",
    "compose.yaml",
    "src",
    "tests",
    "docs/guide",
    "tools",
    "skills",
    "workflows",
    "tuning",
    "calibration",
    "model-catalog",
)
SKIP_PARTS = {"vendor", "__pycache__"}
TEXT_SUFFIXES = {"", ".md", ".py", ".html", ".js", ".scss", ".yaml", ".yml", ".toml", ".pot", ".sh"}


def _files() -> list[Path]:
    found = []
    for root in ROOTS:
        path = REPO_ROOT / root
        candidates = [path] if path.is_file() else path.rglob("*")
        for file in candidates:
            if not file.is_file() or SKIP_PARTS & set(file.parts):
                continue
            if file.suffix in TEXT_SUFFIXES or file.name in {"Dockerfile", "NOTICE"}:
                found.append(file)
    return found


def test_no_typographic_characters_in_published_text() -> None:
    offenders = []
    for file in _files():
        text = file.read_text(encoding="utf-8", errors="ignore")
        for match in FORBIDDEN.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{file.relative_to(REPO_ROOT)}:{line}: U+{ord(match.group()):04X}")
    assert not offenders, "typographic characters in published text:\n" + "\n".join(offenders)
