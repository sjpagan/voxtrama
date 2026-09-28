"""The Recent runs card, as the home page shows it.

Takes RunSummary rows the route has already read from the database
(api.run_views.run_summary builds them, and reusing them avoids deciding
again what a run's list row is, which is already decided) and turns
each into what the template needs: state as the model names it, a tone
for the state's dot, created_at formatted for the request's locale. No
query, no domain decision, only presentation.

`filenames` is the one exception that needs explaining. A row's main
subject is the file someone recognises, not its workflow (the design
shows `team-meeting.wav`, never a workflow name), and that name lives on
Recording, not on Run or RunSummary. Resolving recording_id to
Recording.original_filename is a query, so shell.py, which already holds
the session, does it once for every row and hands this module the result
as plain data. run_views.step_view is handed superseded_by_run_id the
same way instead of looking it up itself.

Importing RunSummary from api crosses from rendering into entrypoints,
the one pairing the layer diagram draws no arrow for. This is
deliberate: the type is a read shape FastAPI's response_model already
commits to, and defining a second one here would be the duplication
this module exists to avoid. run_views sits in api/, not api/routes/:
api/routes/__init__.py imports every router eagerly, and
reaching that package for a response model with no route of its own
turned this crossing into a real cycle whenever rendering was the first
thing imported.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.api.run_views import RunSummary
from voxtrama.db.models.run import RunState
from voxtrama.i18n.formatting import format_datetime
from voxtrama.i18n.translator import Translator

# Which colour a state's dot uses (components/runs_list.html): only the
# two tones this list has ever needed. abstracts/_tokens.scss has also had
# a danger colour (measured for the run page's failed-step
# marker), but nothing here reads it. Every other state, including
# failed, gets None, which the template renders with no colour modifier
# instead of one invented for this list alone.
_STATE_TONE = {
    RunState.SUCCEEDED: "success",
    RunState.RUNNING: "warning",
}


@dataclass(frozen=True)
class RunRow:
    """One run as the home page's Recent runs card shows it.

    `filename` is None, not "", when the run has no Recording (one that
    failed before import ran) or its id no longer matches a Recording.
    The template decides what to say then. This only reports whether
    there is anything to say.

    `href` and `kind` exist for rendering.recent_activity. A plain
    run row leaves `href` unset and the template falls back to
    `/runs/{id}/view`, the only target this module has ever built. A row
    for a Recording with no Run yet sets both, so the template can tell
    the two apart without knowing anything about Recordings.
    """

    id: str
    filename: str | None
    workflow_name: str
    state: str
    state_tone: str | None
    created_at: str
    href: str | None = None
    kind: str = "run"
    label: str | None = None  # The job's own name, when it was given one


def run_rows(
    summaries: list[RunSummary],
    translator: Translator,
    filenames: dict[str, str],
    labels: dict[str, str] | None = None,
) -> list[RunRow]:
    """Turn already-read RunSummary rows into what Recent runs renders.

    `filenames` maps recording_id to Recording.original_filename, for
    every recording_id these summaries reference. shell.py builds it in
    one query instead of this module querying per row.
    """
    return [
        RunRow(
            id=summary.id,
            filename=filenames.get(summary.recording_id) if summary.recording_id else None,
            workflow_name=summary.workflow_name,
            state=summary.state.value,
            state_tone=_STATE_TONE.get(summary.state),
            created_at=format_datetime(translator, summary.created_at),
            label=(labels or {}).get(summary.id),
        )
        for summary in summaries
    ]
