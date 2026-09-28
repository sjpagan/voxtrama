"""components/sidebar.html and components/breadcrumb.html, rendered alone.

Split out of test_web_components.py, the same reason
test_web_run_labels_component.py and test_web_identity_menu.py already give
for their own split: neither file should grow past the project's size limit.
The sidebar went hierarchical here (Setup's own four steps nest under it)
and the breadcrumb is new. Both earned their own file rather than pushing
runs_list's own tests over the cap.
"""

from __future__ import annotations

from gettext import NullTranslations

from voxtrama.api.templating import templates_environment
from voxtrama.i18n.jinja import render_context
from voxtrama.i18n.translator import Translator
from voxtrama.rendering import Crumb, NavItem, sidebar_items

_translator = Translator(locale="en", translations=NullTranslations())


def _module(template_name: str):
    template = templates_environment.get_template(template_name)
    return template.make_module(render_context(_translator))


def test_sidebar_nav_renders_only_sections_with_a_route() -> None:
    """Jobs · Workflow · Settings, and Home before them. Models moved
    inside Settings, so it only shows while Settings is open.
    """
    items = sidebar_items("runs")
    html = str(_module("components/sidebar.html").sidebar_nav(items))

    assert html.count("<a ") == 4
    assert 'href="/"' in html and "Home" in html
    assert 'href="/jobs"' in html
    assert 'href="/workflows"' in html
    assert 'href="/setup"' in html
    assert 'href="/models"' not in html
    assert "Jobs" in html
    assert "Workflow" in html
    assert "Settings" in html
    assert "coming soon" not in html


def test_sidebar_nav_marks_the_active_item() -> None:
    items = [NavItem(key="runs", href="/", active=True)]
    html = str(_module("components/sidebar.html").sidebar_nav(items))

    assert 'aria-current="page"' in html


def test_sidebar_nav_renders_setup_children_only_while_setup_is_active() -> None:
    """No switch makes `Setup` appear any more (it's on every page), but its
    own four children only unfold while one of them is `current`.
    """
    inactive_html = str(_module("components/sidebar.html").sidebar_nav(sidebar_items("runs")))
    active_html = str(
        _module("components/sidebar.html").sidebar_nav(sidebar_items("setup-processing"))
    )

    assert "Local processing" not in inactive_html
    assert "Local processing" in active_html
    assert "Personal settings" not in active_html  # Left the wizard
    assert "Model ready" in active_html
    assert "Private storage" in active_html


def test_sidebar_nav_has_no_separator_when_the_footer_group_is_empty() -> None:
    html = str(_module("components/sidebar.html").sidebar_nav(sidebar_items("runs")))

    assert "vx-nav-separator" not in html


def test_sidebar_nav_renders_a_separator_before_a_non_empty_footer_group() -> None:
    items = [
        NavItem(key="runs", href="/", active=True),
        NavItem(key="settings", href="/settings", active=False, footer=True),
    ]
    html = str(_module("components/sidebar.html").sidebar_nav(items))

    assert "vx-nav-separator" in html


def test_breadcrumb_last_ring_is_current_and_every_ancestor_is_a_link() -> None:
    crumbs = [Crumb(key="runs", href="/"), Crumb(key="run", label="team-meeting.wav")]
    html = str(_module("components/breadcrumb.html").breadcrumb(crumbs))

    assert html.count("<a ") == 1
    assert 'href="/"' in html
    assert "Jobs" in html
    assert 'aria-current="page"' in html
    assert "team-meeting.wav" in html
