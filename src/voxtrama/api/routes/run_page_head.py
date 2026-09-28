"""The head of the job view in every state.

A concluded job already had its own head (title, the settings line,
«Regenerate job»), built from the manifest by api.routes.run_page_result.
A running and a failed job get the same head, so the same two
pieces are read here for them too: the settings line from the manifest the
engine writes before the first step runs (a job still queued has none yet,
and shows its workflow alone), and «Regenerate job» once the job is over
(a running job has nothing to regenerate from yet).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from sqlalchemy.orm import Session

from voxtrama.api.routes.run_page_result import manifest_of, workflow_title
from voxtrama.api.routes.run_regenerate import REGENERABLE_STATES, regenerate_form
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models.run import Run, is_final
from voxtrama.housekeeping.retention import ended, retention_of
from voxtrama.i18n.formatting import format_date
from voxtrama.i18n.translator import Translator
from voxtrama.rendering import ResultView
from voxtrama.rendering.job_settings_line import JobHead, settings_line


def job_head_for(
    settings: Settings,
    run: Run,
    result: ResultView | None,
    session: Session | None = None,
    translator: Translator | None = None,
) -> JobHead:
    """The head for `run`, with how long its data stays when that is known."""
    head = _head(settings, run, result)
    rule = retention_of(session, run, settings.retention_days) if session else None
    if rule is None:
        return head
    deletes = ended(run) + timedelta(days=rule.days) if is_final(run.state) else None
    shown = format_date(translator, deletes) if deletes and translator else None
    return replace(head, retention_days=rule.days, deletes_on=shown)


def _head(settings: Settings, run: Run, result: ResultView | None) -> JobHead:
    """The head for `run`; a concluded job's own is the one its result already built."""
    if result is not None:
        return JobHead(settings=result.settings, regenerate=result.regenerate)
    manifest = manifest_of(get_paths(settings.data_dir).runs_dir, run.id)
    line = settings_line(manifest, workflow_title(run.workflow_name), settings.summary_detail)
    can_regenerate = str(run.state) in REGENERABLE_STATES and run.recording_id is not None
    return JobHead(
        settings=line,
        regenerate=regenerate_form(run, manifest, settings) if can_regenerate else None,
    )
