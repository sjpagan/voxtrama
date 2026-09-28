"""Recent runs and not-yet-started Recordings, merged into one table.

The design has a single `Recent runs` list. The home
page used to render two: runs.run_rows' list, and a second, stateless
one for a Recording nobody has started a Run on yet
(components/recordings_list.html). The design does not have two
lists, and neither carried the state and action each row needs.

That second list is gone. A freshly imported Recording now shows up here
as a row whose state is `"not_started"` and whose action is "Choose
workflow" instead of "View". This is the distinction the two lists
already drew, folded into one table, newest first by each row's own
timestamp (Run.created_at, or Recording.imported_at for one with no Run yet).

`workflow` is what GET / carries in from
pages/workflow_library.html's "Run workflow". A workflow chosen there can
only land on a pending Recording's "Choose workflow" link, so that link
carries the name forward as the same `?workflow=` parameter instead of a
second state this module would have to keep in sync.
api.routes.workflow_choose reads it back off the query string the same
way.
"""

from __future__ import annotations

from urllib.parse import urlencode

from voxtrama.api.run_views import run_summary
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.i18n.formatting import format_datetime
from voxtrama.i18n.translator import Translator
from voxtrama.rendering.runs import RunRow, run_rows


def _pending_row(recording: Recording, translator: Translator, workflow: str | None) -> RunRow:
    """One imported Recording with no Run yet, as the table's own "not started" row."""
    query = f"?{urlencode({'workflow': workflow})}" if workflow else ""
    return RunRow(
        id=recording.id,
        filename=recording.original_filename,
        workflow_name="",
        state="not_started",
        state_tone=None,
        created_at=format_datetime(translator, recording.imported_at),
        href=f"/recordings/{recording.id}/choose-workflow{query}",
        kind="recording",
    )


def recent_activity_rows(
    runs: list[Run],
    pending_recordings: list[Recording],
    translator: Translator,
    filenames: dict[str, str],
    limit: int,
    workflow: str | None = None,
    labels: dict[str, str] | None = None,
) -> list[RunRow]:
    """Merge runs and pending recordings, newest first by their own timestamp, cut to `limit`.

    Both lists arrive already limited to `limit` each (shell.py's
    queries). Merging two short, ordered lists in Python avoids a query
    neither table alone could answer. `workflow` is already checked to
    name a real, loadable workflow by the time it gets here (shell.py's
    check), so it is never carried through unvalidated.
    """
    dated_runs = list(
        zip(
            (run.created_at for run in runs),
            run_rows([run_summary(run) for run in runs], translator, filenames, labels),
            strict=True,
        )
    )
    dated_pending = [
        (recording.imported_at, _pending_row(recording, translator, workflow))
        for recording in pending_recordings
    ]
    merged = sorted(dated_runs + dated_pending, key=lambda dated: dated[0], reverse=True)
    return [row for _, row in merged[:limit]]
