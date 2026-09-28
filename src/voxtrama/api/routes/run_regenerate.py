"""POST /runs/{id}/regenerate: run a concluded job again, choices included.

The «Regenerate job» button of the job view. It replaces the earlier «Change
workflow» panel, which could only switch workflow: here the workflow and
every field of the new-job form can change. The new run
starts on the same Recording with `reused_from_run_id` set, so every step
whose inputs, skill and model are unchanged is adopted from this job
instead of computed again (engine.reuse, keyed by engine.step_hashing's
reuse_key), and a step whose choices changed runs anew.

`regenerate_form` is what the panel starts from: this job's own values,
read from its manifest where it records them, else the installation's.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import DbDep, QueueDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.job_choices import JobForm, job_choices
from voxtrama.api.routes.job_defaults import job_defaults, summary_models, transcription_models
from voxtrama.api.routes.new_job_view import job_workflow_titles
from voxtrama.api.routes.recording_upload_gate import require_ready
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.routes.run_start import _enqueue_or_error
from voxtrama.api.routes.workflow_lookup import load_workflow_or_422
from voxtrama.config.settings import Settings
from voxtrama.db.models.run import Run
from voxtrama.db.people import local_user
from voxtrama.manifest.schema import Manifest
from voxtrama.rendering.job_regenerate import RegenerateForm
from voxtrama.rendering.job_settings_line import settings_line

router = APIRouter()

# A failed or stopped job regenerates too: the steps it finished
# are adopted, the rest run again with whatever the panel changed.
REGENERABLE_STATES = frozenset({"succeeded", "failed", "interrupted", "cancelled"})


def _profile_for(whisper: list[tuple[str, str]], size: str | None) -> str | None:
    """The hardware profile whose Whisper model is `size` (the manifest records the model)."""
    return next((profile for profile, model in whisper if model == size), None)


def regenerate_form(run: Run, manifest: Manifest | None, settings: Settings) -> RegenerateForm:
    """The panel's starting values: what this job ran with."""
    defaults = job_defaults(settings)
    choices = manifest.choices if manifest is not None else None
    environment = manifest.environment if manifest is not None else None
    line = settings_line(manifest, "", defaults.summary_detail)
    whisper = transcription_models()
    return RegenerateForm(
        workflows=tuple(job_workflow_titles(settings).items()),
        workflow_name=run.workflow_name,
        context=(choices.context if choices else None) or "",
        hardware_profile=_profile_for(whisper, line.transcription_model)
        or defaults.hardware_profile,
        parallel_chunks=(environment.num_workers if environment else None)
        or defaults.parallel_chunks,
        cores_per_chunk=(environment.cpu_threads if environment else None)
        or defaults.cores_per_chunk,
        generative_model=line.summary_model or defaults.generative_model,
        summary_detail=(choices.summary_detail if choices else None) or defaults.summary_detail,
        pause_merge_seconds=(choices.pause_merge_seconds if choices else None)
        or defaults.pause_merge_seconds,
        machine_cores=defaults.machine_cores,
        output_language=(choices.output_language if choices else None) or "",
        retention_days=str((choices.retention_days if choices else None) or ""),
        installation_retention_days=defaults.installation_retention_days,
        providers=defaults.providers,
        provider=(choices.provider if choices else None) or defaults.provider,
        whisper_models=tuple(whisper),
        llm_models=tuple(summary_models(settings)),
    )


@router.post("/runs/{run_id}/regenerate", dependencies=[Depends(require_ready)])
async def regenerate_route(
    run_id: str, request: Request, session: DbDep, settings: SettingsDep, queue: QueueDep
) -> RedirectResponse:
    """Start the job again on the same recording, and open the new job's view."""
    run = get_run_or_404(run_id, session)
    if str(run.state) not in REGENERABLE_STATES or run.recording_id is None:
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            title="Only a job that is over can be regenerated",
            detail=f"run '{run_id}' is {run.state}",
        )
    submitted = await request.form()
    form = JobForm.model_validate(
        {key: value for key, value in submitted.items() if isinstance(value, str)}
    )
    workflow = load_workflow_or_422(form.workflow_name)
    # «Run every step again» starts the job with nothing to adopt.
    # It still replaces this one once it succeeds.
    rerun_all = submitted.get("rerun_all") == "true"
    new_run = _enqueue_or_error(
        session,
        queue,
        form.workflow_name,
        workflow,
        run.recording_id,
        job_choices(form, settings),
        local_user(session).id,
        reused_from=None if rerun_all else run.id,
    )
    new_run.label = run.label
    new_run.replaces_run_id = run.id  # Replaces this job once it succeeds
    session.commit()
    return RedirectResponse(f"/runs/{new_run.id}/view", status_code=status.HTTP_303_SEE_OTHER)
