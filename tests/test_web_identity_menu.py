"""components/header.html's identity menu, rendered alone.

Split out of test_web_components.py, the same reason
test_web_run_labels_component.py already gives for its own split: neither
file should grow past the project's size limit. Before this menu the corner
held four separate targets at three different heights: the badge, the
theme disclosure, the identity circle, and a settings gear that led
nowhere. These tests are the ones that would catch the menu quietly
losing one of the commands it swallowed: a theme choice, the link to
/profile, or the Settings entry's own link to
api.routes.setup_settings.
"""

from __future__ import annotations

from gettext import NullTranslations

from voxtrama.api.templating import templates_environment
from voxtrama.i18n.jinja import render_context
from voxtrama.i18n.translator import Translator
from voxtrama.rendering.theme import Theme, theme_choices

_translator = Translator(locale="en", translations=NullTranslations())


def _module(template_name: str):
    template = templates_environment.get_template(template_name)
    return template.make_module(render_context(_translator))


def test_site_header_shows_the_brand_and_the_search() -> None:
    """The fixed "Local" badge gave way to the health pill,
    which needs a reading this bare render does not have, so no pill here
    rather than one that guessed. The navbar gained the search field.
    """
    html = str(_module("components/header.html").site_header())

    assert "Voxtrama" in html
    assert 'action="/search"' in html
    assert "Running locally" not in html


def test_header_actions_shows_the_identity_circle_when_given_an_initial() -> None:
    """The circle is the menu's trigger, not a link of its own any
    more. "Your profile" moved inside the menu it opens.
    """
    html = str(_module("components/header.html").header_actions("GP", "Giorgio Pagano"))

    assert '<span class="vx-avatar" aria-hidden="true">GP</span>' in html
    assert '<a href="/profile" class="vx-identity__link">' in html


def test_header_actions_shows_a_user_icon_without_a_name() -> None:
    """The header shows the circle only when there is a name to
    show. rendering.identity.header_initial returns None for
    this case (no local user yet). The menu itself stays reachable
    even then: the trigger falls back to a plain user icon.
    """
    html = str(_module("components/header.html").header_actions(None, None))

    assert "vx-avatar" not in html
    assert 'class="vx-identity__trigger"' in html


def test_identity_menu_carries_the_three_theme_choices_and_the_profile_link() -> None:
    """The theme control and "Your profile" moved behind the circle,
    they did not vanish. Every choice components/theme_control.html
    offered before still has to be there, now inside this one menu.
    """
    html = str(
        _module("components/header.html").header_actions(
            "GP", "Giorgio Pagano", theme_choices(Theme.DARK), "/"
        )
    )

    assert '<a href="/profile" class="vx-identity__link">' in html
    assert "Your profile" in html
    assert "Light" in html
    assert "Dark" in html
    assert "Auto (follows your system)" in html
    assert html.count('name="theme"') == 3


def test_identity_menu_settings_entry_opens_the_writable_overview() -> None:
    """The gear that led nowhere now opens api.routes.setup_settings,
    the same page Setup's own sidebar entry does (rendering.nav).
    """
    html = str(_module("components/header.html").header_actions("GP", "Giorgio Pagano"))

    assert '<a href="/setup" class="vx-identity__settings">' in html
    assert "Settings" in html


def test_identity_menu_opens_even_with_no_name_written() -> None:
    """No local user has a name yet (the empty state): the menu still
    opens, from the fallback trigger, and its first entry is the way to
    fix that rather than a "Your profile" link with nothing to show.
    """
    html = str(
        _module("components/header.html").header_actions(None, None, theme_choices(Theme.AUTO), "/")
    )

    assert '<details class="vx-identity">' in html
    assert '<a href="/profile" class="vx-identity__link">Add your name</a>' in html
    assert "Your profile" not in html
