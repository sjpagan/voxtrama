"""The sidebar and breadcrumb Setup's own three tuned steps share:
setup_processing.py, setup_models.py and setup_storage.py each render the
same "Setup › <step>" chain and the same four-item nested sidebar, and
each already carries the same three query values (hardware_profile,
cores_per_chunk, parallel_chunks) another of the three needs back.
Writing the wiring once here keeps a route's own `sidebar_items`
call from drifting into a bare link that silently drops them (see
rendering.nav.sidebar_items's own docstring on why that is a real defect,
not a detail). profile.py's own step 1 needs neither: it has nothing yet
to carry, and its breadcrumb is one ring shorter (rendering.Crumb's
`key="setup-personal"` with no sibling step before it), so it builds its
own instead of calling in here.
"""

from __future__ import annotations

from voxtrama.rendering import Crumb, NavItem, sidebar_items

# The first ring is always Setup's own section root, whichever step
# the rest of the chain names: the overview (api.routes.setup_settings),
# not the wizard's own first step. The wizard is something that page
# links to, not the section's own front door.
_SETUP_ROOT = Crumb(key="setup", href="/setup")


def setup_nav_items(current: str, carry: dict[str, object]) -> list[NavItem]:
    """Setup's own sidebar entry, its four steps carrying `carry` forward."""
    return sidebar_items(current, setup_carry=carry)


def setup_breadcrumb(current: str) -> list[Crumb]:
    """`Setup › <step>`, `current` being one of Setup's own four child keys."""
    return [_SETUP_ROOT, Crumb(key=current)]
