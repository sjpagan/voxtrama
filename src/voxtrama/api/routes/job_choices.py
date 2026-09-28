"""The new-job form's fields, and the RunChoices they become.

A field left at its default (api.routes.job_defaults) is no choice at all
and stays None. A field moved off it becomes the job's own choice. The
declared context has no default: empty means none. Every number is
read as text first, so a blank or malformed field is refused with the
field's name rather than a generic parse error.
"""

from __future__ import annotations

from fastapi import status
from pydantic import BaseModel, ValidationError

from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.job_defaults import job_defaults
from voxtrama.config.settings import Settings
from voxtrama.workflow.choices import RunChoices


class JobForm(BaseModel):
    """Everything the new-job form posts besides the files."""

    workflow_name: str = ""
    label: str = ""
    context: str = ""
    transcribe_only: bool = False
    merge: bool = False
    # How several files relate, "sequence" (one after another) or
    # "tracks" (recorded at the same time, mixed into one).
    parts_mode: str = "sequence"
    hardware_profile: str = ""
    parallel_chunks: str = ""
    cores_per_chunk: str = ""
    generative_model: str = ""
    summary_detail: str = ""
    pause_merge_seconds: str = ""
    output_language: str = ""
    retention_days: str = ""  # "" keeps the installation's limit
    provider: str = ""  # A configured provider's name


def _invalid(detail: str) -> ProblemException:
    return ProblemException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_failed",
        title="The job options do not match the expected shape",
        detail=detail,
    )


def _changed(raw: str, default: object, kind: type, field: str) -> object:
    """`raw` as `kind`, or None when blank or equal to `default`."""
    if not raw.strip():
        return None
    try:
        value = kind(raw)
    except ValueError as exc:
        raise _invalid(f"{field}: {raw!r} is not a number") from exc
    return None if value == default else value


def job_choices(form: JobForm, settings: Settings) -> RunChoices:
    """The job's own choices: only what the form moved off this installation's defaults."""
    defaults = job_defaults(settings)
    profile = form.hardware_profile or None
    model = form.generative_model or None
    try:
        return RunChoices(
            hardware_profile=None if profile == defaults.hardware_profile else profile,
            generative_model=None if model == defaults.generative_model else model,
            parallel_chunks=_changed(
                form.parallel_chunks, defaults.parallel_chunks, int, "parallel_chunks"
            ),
            cores_per_chunk=_changed(
                form.cores_per_chunk, defaults.cores_per_chunk, int, "cores_per_chunk"
            ),
            summary_detail=_changed(
                form.summary_detail, defaults.summary_detail, int, "summary_detail"
            ),
            pause_merge_seconds=_changed(
                form.pause_merge_seconds, defaults.pause_merge_seconds, float, "pause"
            ),
            context=form.context.strip() or None,
            output_language=form.output_language or None,
            retention_days=_changed(form.retention_days, None, int, "retention_days"),
            provider=None if form.provider in ("", defaults.provider) else form.provider,
        )
    except ValidationError as exc:
        raise _invalid(str(exc)) from exc
