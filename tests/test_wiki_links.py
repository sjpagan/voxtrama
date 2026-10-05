"""Links, images and the nav-derived names in the generated wiki."""

from __future__ import annotations

from pathlib import Path

import _wiki_build
from _wiki_build import IMAGE_BASE, build

PAGES = {
    "index.md": (
        "Go to [Install](install.md), [the step](install.md#step-one), [Start](sub/new-job.md)\n"
        "and [the site](https://example.org/a.md) or [mail](mailto:a@b.c).\n"
        "A [link that wraps\nover two lines](first-start.md#x) stays a link.\n"
    ),
    "sub/new-job.md": "Back to [Install](../install.md#a) and [Home](../index.md).\n",
    "install.md": "![Shot](images/shot.png) and ![Wide](images/wide.png){ width=600 }\n",
}


def test_links_between_pages_become_wiki_page_names(tmp_path: Path) -> None:
    out, errors = build(tmp_path, PAGES)
    assert errors == []
    home = (out / "Home.md").read_text()
    assert "[Install](Install)" in home
    assert "[the step](Install#step-one)" in home
    assert "[Start](Start-a-job)" in home
    assert "[link that wraps\nover two lines](First-start#x)" in home
    assert "(https://example.org/a.md)" in home and "(mailto:a@b.c)" in home


def test_links_resolve_relative_to_the_page_that_holds_them(tmp_path: Path) -> None:
    out, _ = build(tmp_path, PAGES)
    assert (out / "Start-a-job.md").read_text() == (
        "Back to [Install](Install#a) and [Home](Home).\n"
    )


def test_images_point_at_the_pinned_commit_and_lose_their_attributes(tmp_path: Path) -> None:
    out, _ = build(tmp_path, PAGES)
    assert (out / "Install.md").read_text() == (
        f"![Shot]({IMAGE_BASE}/docs/guide/images/shot.png) and "
        f"![Wide]({IMAGE_BASE}/docs/guide/images/wide.png)\n"
    )


def test_a_link_to_a_page_outside_the_nav_is_an_error(tmp_path: Path) -> None:
    out, errors = build(tmp_path, {"index.md": "See [it](ghost.md).\n"})
    assert len(errors) == 1
    assert "index.md:1" in errors[0] and "ghost.md" in errors[0]
    assert not out.exists()


def test_the_script_exits_non_zero_on_an_unknown_link(tmp_path: Path) -> None:
    config = _wiki_build.make_guide(tmp_path, {"index.md": "[x](ghost.md)\n"})
    args = ["--config", str(config), "--out", str(tmp_path / "w"), "--image-base", IMAGE_BASE]
    assert _wiki_build.build_wiki.main(args) == 1


def test_page_names_drop_what_a_wiki_filename_cannot_hold() -> None:
    assert _wiki_build.build_wiki.page_name('A "b": c/d?') == "A-b-cd"
    assert _wiki_build.build_wiki.page_name("Start a job") == "Start-a-job"
