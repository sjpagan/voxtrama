"""rendering.nav: the sidebar's hierarchy and the breadcrumb's own building block.

components/sidebar.html's own markup is exercised in test_web_components.py
instead. These tests are about what sidebar_items() decides exists, not
how a template draws it.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from voxtrama.rendering.nav import sidebar_items


def _href_params(href: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(href).query)


def test_a_section_with_no_route_and_no_child_does_not_render() -> None:
    """Jobs (key `runs`), Workflow, Settings, and Home before
    them. System and Data & privacy do not come back.
    """
    items = sidebar_items("runs")

    assert [item.key for item in items] == ["home", "runs", "workflows", "settings"]
    assert items[0].href == "/"


def test_setup_is_always_shown_without_any_switch() -> None:
    """The regression this test exists to catch:
    `Setup` used to disappear once setup.is_first_run turned false, which
    left the page describing the four setup steps with no way back into
    them. No caller passes anything to make `Setup` appear any more: it
    is always there, on every page.
    """
    items = sidebar_items("runs")
    setup = next(item for item in items if item.key == "settings")

    # The writable overview is the section's own front door now,
    # first in reading order, Data & privacy next, then the wizard.
    assert [child.key for child in setup.children] == [
        "setup-settings",
        "setup-privacy",
        "setup-processing",
        "setup-model",
        "setup-storage",
        "models",
    ]


def test_setup_itself_links_to_the_writable_overview() -> None:
    """`Setup` used to open the wizard's own first step directly.
    Now it opens the overview that can also relaunch that wizard.
    """
    items = sidebar_items("runs")
    setup = next(item for item in items if item.key == "settings")

    assert setup.href == "/setup"


def test_setup_is_active_when_one_of_its_children_is_current() -> None:
    items = sidebar_items("setup-model")
    setup = next(item for item in items if item.key == "settings")

    assert setup.active is True
    assert [child.key for child in setup.children if child.active] == ["setup-model"]


def test_a_setup_child_carries_the_tuning_values_forward() -> None:
    """The regression this test exists to catch: a bare link here silently drops
    the auto-tuned core/chunk counts /setup/model-ready and
    /setup/private-storage default to 1/1 the moment nothing is supplied.
    """
    carry = {"hardware_profile": "pro", "cores_per_chunk": 4, "parallel_chunks": 2}
    items = sidebar_items("setup-processing", setup_carry=carry)
    setup = next(item for item in items if item.key == "settings")
    by_key = {child.key: child for child in setup.children}

    for key in ("setup-processing", "setup-model", "setup-storage"):
        params = _href_params(by_key[key].href)
        assert params["hardware_profile"] == ["pro"]
        assert params["cores_per_chunk"] == ["4"]
        assert params["parallel_chunks"] == ["2"]
    assert "setup-personal" not in by_key  # The name is asked when needed


def test_without_carry_a_setup_child_links_bare() -> None:
    items = sidebar_items("setup-processing")
    setup = next(item for item in items if item.key == "settings")
    processing = next(child for child in setup.children if child.key == "setup-processing")

    assert processing.href == "/setup/local-processing"


def test_models_is_a_child_of_settings_and_marks_itself_current() -> None:
    """Models moved inside Settings, and takes no tuning carry."""
    items = sidebar_items("models", setup_carry={"hardware_profile": "pro"})
    settings = next(item for item in items if item.key == "settings")
    models = next(child for child in settings.children if child.key == "models")

    assert models.href == "/models"
    assert models.active is True
    assert settings.active is True


def test_workflows_links_to_its_own_route_and_marks_itself_current() -> None:
    items = sidebar_items("workflows")
    workflows = next(item for item in items if item.key == "workflows")

    assert workflows.href == "/workflows"
    assert workflows.active is True
