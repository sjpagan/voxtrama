"""record_context_budget: what one generative call's num_ctx choice was, written to the row.

Split from progress.py, which owns every other RunStep write point, to
keep that file under the project's size limit. progress_file.py sits apart
for the same reason.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from voxtrama.db.models.step import RunStep


def record_context_budget(
    session: Session,
    row: RunStep,
    *,
    context_window_tokens: int,
    context_window_at_risk: bool,
    output_resumptions: int | None,
) -> None:
    """Write the num_ctx a generative call used, and commit it immediately.

    Called twice by engine.generative._generate_and_record: once as soon
    as the budget is computed, so `context_window_at_risk` reaches the
    manifest even on a call that never comes back cleanly, and once more
    with `output_resumptions` filled in once resuming has run its course.
    Committed immediately, as in engine.progress.record_provenance: the
    process can die before this step's outcome is decided.
    """
    row.context_window_tokens = context_window_tokens
    row.context_window_at_risk = context_window_at_risk
    row.output_resumptions = output_resumptions
    session.commit()
