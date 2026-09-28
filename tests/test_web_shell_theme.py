"""Dark is the default, not an equal option behind a media query.

Split from test_web_shell.py (the project's ~150-line file limit) because this
file is entirely about the cascade in the generated CSS, not the template
that loads it.

Four states, and each test below pins one of them. The fourth (an explicit
light choice on a machine whose system says dark) is the one that is
invisible to a browser check run on a light machine, because there the media
query covers it. It went missing once for that reason.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = REPO_ROOT / "src" / "voxtrama" / "web" / "static" / "css" / "voxtrama.min.css"

DARK_BACKGROUND = "--vx-bg: #050c1d"
LIGHT_BACKGROUND = "--vx-bg: #f6fbfe"


def _css() -> str:
    """The generated stylesheet with its comments stripped.

    The banner comment names selectors in prose, and a substring search for
    one would otherwise match the explanation instead of the rule.
    """
    return re.sub(r"/\*.*?\*/", "", CSS_PATH.read_text(encoding="utf-8"), flags=re.S)


def _block_after(css: str, selector: str) -> str:
    start = css.index(selector)
    return css[start : css.index("}", start)]


def test_dark_is_the_unconditional_default() -> None:
    """No choice and no system preference still renders dark."""
    css = _css()
    assert DARK_BACKGROUND in _block_after(css, ":root{")


def test_a_light_system_gets_the_light_palette() -> None:
    css = _css()
    media = "@media(prefers-color-scheme: light){:root:not([data-theme=dark])"
    assert LIGHT_BACKGROUND in _block_after(css, media)


def test_explicit_dark_wins_over_a_light_system() -> None:
    """Same specificity as the media block, so it has to come after it."""
    css = _css()
    assert css.index("@media(prefers-color-scheme: light)") < css.index(":root[data-theme=dark]{")
    assert DARK_BACKGROUND in _block_after(css, ":root[data-theme=dark]{")


def test_explicit_light_is_covered_on_a_system_that_prefers_dark() -> None:
    """The mirror of the test above, and the state that once matched nothing.

    On a machine whose system says dark, the media block never runs. Without
    a rule of its own, `data-theme="light"` would match no block at all:
    every --vx-* would be undefined and the page would fall through to
    Pico's own colours, silently.
    """
    css = _css()
    assert LIGHT_BACKGROUND in _block_after(css, ":root[data-theme=light]{")


def test_color_scheme_states_the_theme_that_resolved() -> None:
    """Never `dark light`: that lets native widgets follow the system.

    Scrollbars and form widgets would then render light on a dark page
    whenever someone picks dark on a light machine: the palette says one
    thing and the chrome around it says another.
    """
    css = _css()
    assert "color-scheme:dark light" not in css
    assert "color-scheme:dark" in _block_after(css, ":root{")
    assert "color-scheme:light" in _block_after(css, ":root[data-theme=light]{")
    assert "color-scheme:dark" in _block_after(css, ":root[data-theme=dark]{")


def test_pico_custom_properties_are_remapped_to_voxtrama_tokens() -> None:
    """Every native Pico control follows the voxtrama palette, not its own."""
    css = _css()
    remapped = [
        "--pico-background-color: var(--vx-bg)",
        "--pico-card-background-color: var(--vx-surface)",
        "--pico-color: var(--vx-text)",
        "--pico-muted-color: var(--vx-text-muted)",
        "--pico-muted-border-color: var(--vx-border)",
        "--pico-primary: var(--vx-primary)",
        "--pico-primary-hover: var(--vx-primary-hover)",
        "--pico-primary-background: var(--vx-primary)",
        "--pico-primary-hover-background: var(--vx-primary-hover)",
        "--pico-form-element-background-color: var(--vx-bg-elevated)",
        "--pico-form-element-border-color: var(--vx-border)",
    ]
    for declaration in remapped:
        assert declaration in css, declaration


def test_every_token_is_defined_in_every_theme() -> None:
    """A token declared in one theme only is undefined in the others.

    The dark theme's background glow was such a token: dark-only, so any
    rule reading it would have resolved to nothing on a light system: a
    colour that silently disappears rather than changing. A palette is a
    vocabulary published for the components that come later, so a token
    nothing reads yet is fine. A token that exists in one state and not in
    another is not.
    """
    css = _css()
    blocks = {
        "dark default": _block_after(css, ":root{"),
        "light system": _block_after(
            css, "@media(prefers-color-scheme: light){:root:not([data-theme=dark])"
        ),
        "explicit dark": _block_after(css, ":root[data-theme=dark]{"),
        "explicit light": _block_after(css, ":root[data-theme=light]{"),
    }
    declared = {name: set() for name in set(re.findall(r"(--vx-[a-z0-9-]+):", css))}
    for label, block in blocks.items():
        for name in re.findall(r"(--vx-[a-z0-9-]+):", block):
            declared[name].add(label)
    partial = {name: sorted(where) for name, where in declared.items() if len(where) != 4}
    assert not partial, f"tokens missing from some themes: {partial}"
