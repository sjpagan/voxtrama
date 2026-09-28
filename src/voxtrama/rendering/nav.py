"""The sidebar's sections and Crumb, the breadcrumb's
building block.

**Current layout**: three sections, Jobs (key `runs`), Workflow, Settings.
Settings carries Setup's former children plus Models. Keys and routes are
unchanged. The history below explains why those children exist.

Structure only: which sections exist, their fixed reading order, which
carry children, which belong to the footer group, and which one (or
which one's child) is current. The label each key shows, the "Setup ▾"
caret and the breadcrumb's {% trans %} label all live in
components/sidebar.html and components/breadcrumb.html. Text is a
template concern, not this module's.

The sidebar first had five permanent sections. `Setup`, the sixth, was
first added as temporary, shown only while setup.is_first_run said the
configuration file was still missing. That was later retracted: a bar that
hides the section the page itself belongs to is worse than an incomplete
one, and the four steps must stay reachable *after* the first run too
(rerunning auto-tune on a changed machine, swapping the generative model).
So `Setup` is now permanent like the other five, and this module has no
switch deciding whether to show it. `data-privacy` also moves inside
`Settings`, the footer group below.

A section with no href and no child with an href does not render at all
(a section stays this way until it gets a route; `workflows` joined the
rendered set once /workflows existed). components/sidebar.html has no
"coming soon" branch left to fall back to. `models` joined the rendered
set as the permanent library of what is downloaded, its state and
its licences. No card, no choice, so it needed no children like `setup`.

The four wizard steps were `setup`'s only children, and none was a
place to change a choice already made. `setup-settings` is the fifth,
first in reading order and what `Setup` now opens (api.routes.setup_settings).
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.rendering.breadcrumb import Crumb

__all__ = ["Crumb"]  # re-exported for callers that imported it from here
from urllib.parse import urlencode

# Top-level reading order. `home` is the new-job page.
_SECTIONS = ("home", "runs", "workflows", "settings")
_FOOTER: set[str] = set()

# `setup` opens the overview the wizard is reached from, not its
# first step. `workflows` only ever lacked a route.
_HREFS = {
    "home": "/",
    "runs": "/jobs",
    "workflows": "/workflows",
    "settings": "/setup",
}

# Settings' children: the overview, Data & privacy, then the
# four wizard steps in the step chain's order. Each is key, base path, and
# the query parameters that path needs regardless of `setup_carry`.
_SETUP_STEPS = (
    ("setup-settings", "/setup", {}),
    ("setup-privacy", "/setup/privacy", {}),
    ("setup-processing", "/setup/local-processing", {}),
    ("setup-model", "/setup/model-ready", {}),
    ("setup-storage", "/setup/private-storage", {}),
    ("models", "/models", {}),
)


@dataclass(frozen=True)
class NavItem:
    """One sidebar entry: which section, where it links (if anywhere),
    whether it's current, its children (Setup's four steps, empty for
    every other entry today) and whether it belongs to the footer group.
    """

    key: str
    href: str | None
    active: bool
    children: tuple[NavItem, ...] = ()
    footer: bool = False


@dataclass(frozen=True)
class BackLink:
    """The "climb back to the list this page belongs to" link
    ("← All runs").

    `key` picks the translated label components/back_link.html shows.
    English text stays out of routes the same way nav_label
    keeps it out of this module. Only `href` is the route's call, for the
    reason sidebar_items's docstring gives for `current`.
    """

    key: str
    href: str


def _setup_children(current: str, setup_carry: dict[str, object] | None) -> tuple[NavItem, ...]:
    """Settings' children. The setup steps carry `setup_carry` forward
    (sidebar_items's docstring says why a bare link here is a real defect).
    """
    children = []
    for key, path, base_params in _SETUP_STEPS:
        carry = setup_carry if setup_carry and key.startswith("setup-") else {}
        params = {**base_params, **carry} if carry else base_params
        href = f"{path}?{urlencode(params)}" if params else path
        children.append(NavItem(key=key, href=href, active=key == current))
    return tuple(children)


def sidebar_items(
    current: str,
    *,
    setup_carry: dict[str, object] | None = None,
) -> list[NavItem]:
    """The sidebar entries, in their fixed order, marking `current` (or
    whichever of Setup's children matches it) as active.

    `Setup` is always included, like every other section in `_SECTIONS`.
    The module docstring says why no page decides whether to show it.
    `setup_carry` is the three values (hardware_profile, cores_per_chunk,
    parallel_chunks) a setup route already carries in its query string.
    Without it, Setup's children link to /setup/model-ready and
    /setup/private-storage *bare*, which silently drops the auto-tuned
    core/chunk counts: those two routes default to 1/1 when nothing is
    supplied. Only the four setup routes have those values to pass. Every
    other page leaves this at None.
    """
    items = []
    for key in _SECTIONS:
        children = _setup_children(current, setup_carry) if key == "settings" else ()
        href = _HREFS.get(key)
        if href is None and not children:
            continue
        active = key == current or any(child.active for child in children)
        items.append(
            NavItem(key=key, href=href, active=active, children=children, footer=key in _FOOTER)
        )
    return items
