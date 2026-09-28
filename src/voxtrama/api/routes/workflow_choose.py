"""GET /recordings/{recording_id}/choose-workflow: the missing link between an
imported Recording and a Run.

A dedicated route, not a panel folded into the home page: a Recording's
row is one click away from a page whose only job is this choice, the same
shape /runs/{id}/view already gives a run in progress and /profile
gives the one thing it edits: one small page per decision,
rather than the home page growing a collapsible section for each of them.

The panel itself (components/workflow_choice_panel.html) takes no opinion
about a Recording at all: the Workflows section reuses the exact same
macro to offer the same choice starting from the library instead, passing
its own `action` and `hidden_fields`. This route only supplies those two
things and the list of offers, which run_start.py's POST consumes on the
other side of the same form.

Every workflow engine.catalog.list_workflow_names finds is shown, in
alphabetical order, never a hand-written list of four: a workflow the
package ships or the user duplicated appears here the moment
its file exists, with no second place to remember to update.

`workflow` is the name a person already picked
before landing here: either in the library, forwarded through GET /'s
own pending-Recording link (rendering.recent_activity), or off "Re-run
with a different workflow" on a succeeded run's own page
(api.routes.run_page_result). Only ever pre-selects one of `offers`
already offers. An unrecognised name is dropped rather than carried
into the panel as if it named something real.

Which of those two doors a person came through is not a second
parameter to remember to keep in sync: a Recording workflow_choose_
history.has_prior_run finds already has a Run is one only "Re-run" could
have reached (GET /'s own pending list, api.routes.shell, never shows a
Recording that already has one), so that alone tells the two apart, for
the crumb trail back (library, only from the first door: arriving from
the library with a workflow already chosen) and for the honest notice (only from the second: nothing
already computed is reused by the plain POST /recordings/{id}/runs this
page's own panel still submits to, engine.enqueue.enqueue_run's
`reused_from_run_id` is never passed here the way api.routes.run_retry
passes it).

The three queries this route needs about a Recording's own history
(whether it already has a Run, whether it has been transcribed, which
workflow already has a result) live in workflow_choose_history.py,
split out to keep this file under the project's file-length limit.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.recording_lookup import get_recording_or_404
from voxtrama.api.routes.workflow_choices import workflow_choices_for
from voxtrama.api.routes.workflow_choose_history import already_run, has_prior_run, transcribed
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.config.settings import Settings
from voxtrama.engine.catalog import WorkflowNotFoundError, list_workflow_names, load_named_workflow
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import (
    Crumb,
    WorkflowOffer,
    build_offer,
    failed_offer,
    recording_rows,
    sidebar_items,
    stored_theme,
    theme_choices,
)
from voxtrama.workflow.errors import WorkflowError

router = APIRouter()


def _build_offers(settings: Settings) -> list[WorkflowOffer]:
    """One WorkflowOffer per name list_workflow_names finds, a failed_offer for one
    that will not even load, never an exception that takes the whole page down with it.
    """
    offers: list[WorkflowOffer] = []
    for name in list_workflow_names():
        try:
            workflow = load_named_workflow(name)
        except (WorkflowNotFoundError, WorkflowError) as exc:
            offers.append(failed_offer(name, str(exc)))
            continue
        choices = workflow_choices_for(workflow)
        offers.append(
            build_offer(workflow, choices, settings.hardware_profile, settings.ollama_model)
        )
    return offers


def _breadcrumb(selected: str | None, came_from_library: bool) -> list[Crumb]:
    """Runs > Choose workflow, unchanged, unless `selected` was carried in from
    the library and nothing is being re-run: then the climb back leads there instead,
    still naming the workflow that started this."""
    if came_from_library:
        crumb = Crumb(key="workflows", href=f"/workflows?workflow={selected}")
        return [crumb, Crumb(key="choose-workflow")]
    return [Crumb(key="runs", href="/jobs"), Crumb(key="choose-workflow")]


@router.get("/recordings/{recording_id}/choose-workflow", response_class=HTMLResponse)
def choose_workflow_page(
    recording_id: str,
    translator: TranslatorDep,
    session: DbDep,
    settings: SettingsDep,
    workflow: str | None = None,
) -> HTMLResponse:
    """Render every workflow's offer for `recording_id`, so a run can start from here."""
    recording = get_recording_or_404(recording_id, session)
    offers = _build_offers(settings)
    selected = workflow if workflow in {offer.name for offer in offers} else None
    is_rerun = has_prior_run(session, recording_id)
    context = page_context(
        session,
        translator,
        settings=settings,
        nav_items=sidebar_items("runs"),
        recording=recording_rows([recording], translator, transcribed(session, recording_id))[0],
        offers=offers,
        selected=selected,
        is_rerun=is_rerun,
        already_run=already_run(session, recording_id),
        theme_choices=theme_choices(stored_theme(session)),
        origin=f"/recordings/{recording_id}/choose-workflow",
        breadcrumb=_breadcrumb(selected, came_from_library=bool(selected) and not is_rerun),
    )
    template = templates_environment.get_template("pages/choose_workflow.html")
    return HTMLResponse(template.render(**context))
