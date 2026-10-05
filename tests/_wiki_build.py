"""Shared fixture for the wiki generator tests.

scripts/ is not a package, so the generator is loaded from its path, and a
small guide (a mkdocs.yml and a few pages) is written under tmp_path to run
it on. Not a test module itself: pytest only collects test_*.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMAGE_BASE = "https://raw.githubusercontent.com/owner/repo/abc123"

_spec = importlib.util.spec_from_file_location(
    "build_wiki", REPO_ROOT / "scripts" / "build_wiki.py"
)
build_wiki = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_wiki)

NAV = """\
nav:
  - Home: index.md
  - Getting started:
      - Install: install.md
      - First start: first-start.md
  - Using:
      - Start a job: sub/new-job.md
  - Troubleshooting: troubleshooting.md
"""


def make_guide(root: Path, pages: dict[str, str], nav: str = NAV) -> Path:
    """Write mkdocs.yml and the pages under root; return the config path."""
    (root / "mkdocs.yml").write_text("docs_dir: docs/guide\n" + nav, encoding="utf-8")
    for name in (
        "index.md",
        "install.md",
        "first-start.md",
        "sub/new-job.md",
        "troubleshooting.md",
    ):
        path = root / "docs" / "guide" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pages.get(name, "# " + name + "\n"), encoding="utf-8")
    return root / "mkdocs.yml"


def build(root: Path, pages: dict[str, str], **kwargs) -> tuple[Path, list[str]]:
    """Run the generator on a small guide; return the output folder and the errors."""
    out = root / "wiki"
    errors = build_wiki.build(make_guide(root, pages, **kwargs), out, IMAGE_BASE)
    return out, errors
