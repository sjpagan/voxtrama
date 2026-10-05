"""Admonitions, keys, attribute lists and fences in the generated wiki."""

from __future__ import annotations

from pathlib import Path

from _wiki_build import build


def _home(tmp_path: Path, text: str) -> str:
    out, errors = build(tmp_path, {"index.md": text})
    assert errors == []
    return (out / "Home.md").read_text()


def test_an_admonition_with_a_title_becomes_an_alert(tmp_path: Path) -> None:
    text = '!!! tip "The chip"\n    First line.\n\n    Second [link](install.md).\n\nAfter.\n'
    assert _home(tmp_path, text) == (
        "> [!TIP]\n> **The chip**\n>\n> First line.\n>\n> Second [link](Install).\n\nAfter.\n"
    )


def test_an_admonition_without_a_title_has_no_title_line(tmp_path: Path) -> None:
    assert _home(tmp_path, "!!! note\n    Body.\n") == "> [!NOTE]\n> Body.\n"


def test_admonition_types_map_to_alert_kinds(tmp_path: Path) -> None:
    kinds = {"warning": "WARNING", "danger": "CAUTION", "error": "CAUTION", "failure": "CAUTION"}
    kinds |= {"important": "IMPORTANT", "tip": "TIP", "mystery": "NOTE"}
    for kind, alert in kinds.items():
        assert _home(tmp_path, f"!!! {kind}\n    Body.\n").startswith(f"> [!{alert}]\n")


def test_keys_become_kbd_elements_but_not_inside_code(tmp_path: Path) -> None:
    text = "Press ++ctrl+c++ or ++esc++, not `++ctrl+c++`.\n"
    assert _home(tmp_path, text) == (
        "Press <kbd>Ctrl</kbd>+<kbd>C</kbd> or <kbd>Esc</kbd>, not `++ctrl+c++`.\n"
    )


def test_attribute_lists_after_headings_go_but_placeholders_stay(tmp_path: Path) -> None:
    text = "## Title { #custom .cls }\n\nUse `{transcript}` and {language} here.\n"
    assert _home(tmp_path, text) == "## Title\n\nUse `{transcript}` and {language} here.\n"


def test_code_fences_are_left_untouched(tmp_path: Path) -> None:
    fenced = "```\n!!! note\n    x\n[a](ghost.md) ++ctrl+c++ ![i](images/a.png){ w=1 }\n```\n"
    assert _home(tmp_path, f"Before [i](install.md)\n{fenced}") == f"Before [i](Install)\n{fenced}"


def test_details_and_tabs_are_refused(tmp_path: Path) -> None:
    for syntax in ('??? note "Fold"\n    x\n', '=== "Tab"\n    x\n'):
        _, errors = build(tmp_path, {"index.md": syntax})
        assert len(errors) == 1 and "unsupported" in errors[0]
