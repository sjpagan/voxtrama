"""GET /runs/{id}/view's own fallback chain, for the moment right after
`Start run`'s redirect.

Split out of api.routes.run_page to keep that file under the project's file
limit, the same reason api.routes.run_page_failure and .run_page_result
already are their own modules.

engine.progress.record_planned_steps writes a RunStep row per step only
once the worker picks the job up, a beat after `Start run`'s own
303 already sent the browser here. A person landing on the page inside
that gap used to see no chain at all: measured on a real run, [data-
step-id] absent from the DOM for 32 seconds while RunStep already held
three rows in the database, because static/js/run_page.js's own
applyStepChain() only updates elements already in the DOM, never adds one.
It went unnoticed until now because a short recording's own run finishes
and reloads to `final` before anyone reads the page in that window.

rendering.run_step_row.resolved_step_rows is where the fallback and the
real rows meet. This module only supplies its second input, read
here because loading a workflow file is the kind of filesystem
work kept out of rendering.
"""

from __future__ import annotations

from voxtrama.db.models.run import Run
from voxtrama.engine.catalog import WorkflowNotFoundError, load_named_workflow
from voxtrama.workflow.definition import Step
from voxtrama.workflow.errors import WorkflowError


def planned_workflow_steps_for(run: Run, have_rows: bool) -> list[Step]:
    """`run.workflow_name`'s own declared steps, or [] once real RunStep
    rows exist (`have_rows`) or when the workflow itself fails to load
    (deleted, or edited into something invalid since the run started):
    the same page this route rendered before this fallback existed, not a
    500 for a run otherwise fine to show.
    """
    if have_rows:
        return []
    try:
        return load_named_workflow(run.workflow_name).steps
    except (WorkflowNotFoundError, WorkflowError):
        return []
