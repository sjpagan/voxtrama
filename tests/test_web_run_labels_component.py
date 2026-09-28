"""components/run_labels.html's own macros, rendered alone.

Split from test_web_components.py, which covers every other shell
component, kept apart so neither file grows past the project's size limit.
static/js/run_page.js reads label_catalog()'s markup instead of carrying
its own English dictionary; a code review is why
that markup, and these tests, exist at all.
"""

from __future__ import annotations

from gettext import NullTranslations

from voxtrama.api.templating import templates_environment
from voxtrama.i18n.jinja import render_context
from voxtrama.i18n.translator import Translator

_translator = Translator(locale="en", translations=NullTranslations())


def _module():
    template = templates_environment.get_template("components/run_labels.html")
    return template.make_module(render_context(_translator))


def test_step_label_translates_the_raw_state() -> None:
    html = str(_module().step_label("running"))

    assert html == "In progress"


def test_run_state_label_translates_the_raw_state() -> None:
    html = str(_module().run_state_label("interrupted"))

    assert html == "Interrupted"


def test_label_catalog_renders_one_translated_entry_per_state() -> None:
    html = str(_module().label_catalog(["pending", "running"], ["running", "failed"]))

    assert '<li data-catalog="step" data-state="pending">Waiting</li>' in html
    assert '<li data-catalog="run" data-state="failed">Failed</li>' in html
