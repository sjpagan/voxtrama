"""Each shell component rendered alone, with only its own parameters.

Same throwaway-Environment approach as test_web_shell.py:23, but reused
against the real, i18n-installed Environment the app renders with
(voxtrama.api.templating) so {% trans %} works the way it does in
production. A {% macro %} component's payoff over {% include %} is
this: its inputs are explicit, so a test supplies them without a
route, a database, or base.html.

components/run_labels.html's own macros are tested in
test_web_run_labels_component.py instead of here, components/header.html's
identity menu in test_web_identity_menu.py, and components/sidebar.html
and components/breadcrumb.html in test_web_sidebar_component.py, kept
apart so neither file grows past the project's size limit.
"""

from __future__ import annotations

from gettext import NullTranslations

from voxtrama.api.templating import templates_environment
from voxtrama.i18n.jinja import render_context
from voxtrama.i18n.translator import Translator
from voxtrama.rendering import RunRow

_translator = Translator(locale="en", translations=NullTranslations())


def _module(template_name: str):
    template = templates_environment.get_template(template_name)
    return template.make_module(render_context(_translator))


def test_runs_list_renders_a_row_per_run() -> None:
    runs = [
        RunRow(
            id="r1",
            filename="team-meeting.wav",
            workflow_name="demo",
            state="succeeded",
            state_tone="success",
            created_at="Jan 1, 2026",
        )
    ]
    html = str(_module("components/runs_list.html").runs_list(runs))

    assert "team-meeting.wav" in html
    assert "demo" in html
    # "succeeded" is the raw RunState value; the word the page shows for it
    # is "Completed", which the template maps to before rendering.
    assert "Completed" in html


def test_runs_list_shows_the_job_s_own_name_before_its_file() -> None:
    runs = [
        RunRow(
            id="r1",
            filename="team-meeting.wav",
            workflow_name="meeting-decisions",
            state="running",
            state_tone=None,
            created_at="Jan 1, 2026",
            label="Weekly product sync",
        )
    ]
    titles = {"meeting-decisions": "Meeting decisions"}
    html = str(_module("components/runs_list.html").runs_list(runs, titles))

    assert "Weekly product sync" in html
    assert "team-meeting.wav" not in html
    assert "Meeting decisions" in html


def test_runs_list_names_a_run_with_no_recording_honestly() -> None:
    runs = [
        RunRow(
            id="r1",
            filename=None,
            workflow_name="demo",
            state="failed",
            state_tone=None,
            created_at="Jan 1, 2026",
        )
    ]
    html = str(_module("components/runs_list.html").runs_list(runs))

    assert "No recording" in html


def test_runs_list_explains_when_there_are_none() -> None:
    html = str(_module("components/runs_list.html").runs_list([]))

    assert "No jobs yet. The first one starts from the form above." in html


def test_runs_list_row_links_to_the_run_page() -> None:
    runs = [
        RunRow(
            id="r1",
            filename="team-meeting.wav",
            workflow_name="demo",
            state="succeeded",
            state_tone="success",
            created_at="Jan 1, 2026",
        )
    ]
    html = str(_module("components/runs_list.html").runs_list(runs))

    assert 'href="/runs/r1/view"' in html
