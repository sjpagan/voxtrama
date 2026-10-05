"""The files around the pages: sidebar, footer, cleaning, and the real guide."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from _wiki_build import IMAGE_BASE, REPO_ROOT, build, build_wiki


def test_the_sidebar_follows_the_nav_with_sections_as_bold_headers(tmp_path: Path) -> None:
    out, _ = build(tmp_path, {})
    assert (out / "_Sidebar.md").read_text() == (
        "- [Home](Home)\n"
        "- **Getting started**\n"
        "  - [Install](Install)\n"
        "  - [First start](First-start)\n"
        "- **Using**\n"
        "  - [Start a job](Start-a-job)\n"
        "- [Troubleshooting](Troubleshooting)\n"
    )


def test_the_footer_says_the_wiki_is_generated(tmp_path: Path) -> None:
    out, _ = build(tmp_path, {})
    footer = (out / "_Footer.md").read_text()
    assert "generated from `docs/guide`" in footer and "pull requests" in footer


def test_stale_pages_go_and_the_git_folder_stays(tmp_path: Path) -> None:
    out = tmp_path / "wiki"
    (out / ".git").mkdir(parents=True)
    (out / ".git" / "keep.md").write_text("x")
    (out / "Old-page.md").write_text("gone")
    (out / "image.png").write_text("not markdown")
    out, errors = build(tmp_path, {})
    assert errors == []
    assert not (out / "Old-page.md").exists()
    assert (out / ".git" / "keep.md").exists() and (out / "image.png").exists()


def test_a_failed_build_leaves_the_existing_wiki_alone(tmp_path: Path) -> None:
    out = tmp_path / "wiki"
    out.mkdir()
    (out / "Old-page.md").write_text("kept")
    build(tmp_path, {"index.md": "[x](ghost.md)\n"})
    assert (out / "Old-page.md").read_text() == "kept"


def test_the_real_guide_converts_to_one_page_per_nav_entry(tmp_path: Path) -> None:
    config = REPO_ROOT / "mkdocs.yml"
    out = tmp_path / "wiki"
    assert build_wiki.build(config, out, IMAGE_BASE) == []
    nav = yaml.safe_load(config.read_text())["nav"]
    names = build_wiki.page_names(build_wiki.flatten_nav(nav))
    assert len(names) >= 10
    for name in names.values():
        assert (out / f"{name}.md").is_file(), name
    guide_link = re.compile(r"\]\([^)]*\.md(#[^)]*)?\)")
    for page in out.glob("*.md"):
        text = page.read_text()
        assert not guide_link.search(text), page.name
        assert "!!!" not in text, page.name
