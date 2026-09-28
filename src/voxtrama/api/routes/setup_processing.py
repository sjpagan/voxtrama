"""GET and POST /setup/local-processing: step 2 of the guided setup.

The page shows the machine read once (diagnostics.machine.read_machine), the three hardware
profiles with their real cost (setup.profile_offers), and the Fine-tune panel's arithmetic
(tuning.chunk_tuning), all through rendering.setup_processing, so this route only reads and hands
off.

**Correction, 2026-09-24**: a blocking download inside the POST sat inside gunicorn's own
120-second worker timeout (Dockerfile), and whisper-medium alone needs more at the floor
bandwidth engine.timeout already assumes: two profiles out of three always timed out. The POST
now only enqueues (queue.submit_download, "create then submit" like engine.enqueue_run) and
redirects immediately, like profile.py's own 303. The worker downloads in the background
(worker.tasks.download_model_job), publishing progress the way a Run already does
(setup.download_progress, on engine.progress_file). GET reads that state: the downloading
panel's bar and log while it runs, the normal cards once done, polled by a plain
`<meta http-equiv="refresh">`: HTML, not JavaScript.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from voxtrama.api.deps import DbDep, QueueDep, SettingsDep
from voxtrama.api.routes.setup_nav import setup_breadcrumb, setup_nav_items
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.diagnostics.machine import read_machine
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import (
    chunk_plan_view,
    download_view,
    machine_summary,
    profile_offer_views,
    setup_step_rows,
    stored_theme,
    theme_choices,
)
from voxtrama.setup import (
    IN_PROGRESS_STATES,
    publish_download_state,
    read_download_state,
    write_download_job_id,
)
from voxtrama.setup.profile_offers import PROFILE_KEYS, build_profile_offers, recommended_key
from voxtrama.transcription.asr import weights_for
from voxtrama.tuning.core_budget import plan_for
from voxtrama.tuning.selector import select_tuning
from voxtrama.weights import is_cached

router = APIRouter()

PATH = "/setup/local-processing"
CANCEL_PATH, REMOVE_PATH = f"{PATH}/cancel-download", f"{PATH}/remove-model"
MODEL_READY_PATH = "/setup/model-ready"


def _carry(hardware_profile: str, cores_per_chunk: int, parallel_chunks: int) -> dict[str, object]:
    return {
        "hardware_profile": hardware_profile,
        "cores_per_chunk": cores_per_chunk,
        "parallel_chunks": parallel_chunks,
    }


@router.get(PATH, response_class=HTMLResponse)
def local_processing_page(
    session: DbDep,
    settings: SettingsDep,
    translator: TranslatorDep,
    hardware_profile: str | None = None,
    cores_per_chunk: int | None = None,
    parallel_chunks: int | None = None,
    error: str | None = None,
) -> HTMLResponse:
    machine = read_machine(settings.data_dir)
    tuning = select_tuning(machine)
    offers = build_profile_offers(machine)
    chosen = hardware_profile if hardware_profile in PROFILE_KEYS else recommended_key(offers)
    # The cap is the machine's own core count: performance cores where the
    # platform separates them, since an efficiency core taken for a
    # transcription chunk slows the chunk instead of adding to it.
    plan = plan_for(machine, tuning, cores_per_chunk, parallel_chunks)
    chosen_offer = next(offer for offer in offers if offer.key == chosen)
    state = read_download_state(settings.data_dir)
    downloading = state is not None and state.state in IN_PROGRESS_STATES
    cached_keys = {o.key for o in offers if is_cached(weights_for(o.key), settings.models_dir)}
    fields = _carry(chosen, plan.cores_per_chunk, plan.parallel_chunks)
    template = templates_environment.get_template("pages/setup_local_processing.html")
    return HTMLResponse(
        template.render(
            **page_context(
                session,
                translator,
                settings=settings,
                nav_items=setup_nav_items("setup-processing", fields),
                wizard_steps=setup_step_rows("processing"),
                machine_line=machine_summary(machine),
                offers=profile_offer_views(offers, machine.free_disk_bytes, cached_keys),
                chosen_profile=chosen,
                chunk_plan=chunk_plan_view(plan, chosen_offer.download_bytes),
                download_error=error,
                downloading=downloading,
                download=download_view(state) if state is not None else None,
                model_ready=chosen in cached_keys,
                model_ready_path=f"{MODEL_READY_PATH}?{urlencode(fields)}",
                cancel_path=CANCEL_PATH,
                remove_path=REMOVE_PATH,
                theme_choices=theme_choices(stored_theme(session)),
                origin=PATH,
                breadcrumb=setup_breadcrumb("setup-processing"),
            )
        )
    )


@router.post(PATH)
def download_selected_model(
    settings: SettingsDep,
    queue: QueueDep,
    hardware_profile: Annotated[str, Form()],
    cores_per_chunk: Annotated[int, Form()],
    parallel_chunks: Annotated[int, Form()],
    return_to: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    """Enqueue the chosen profile's weights download, and return immediately.

    `return_to="/"` (home's first-run card) comes back home, nothing else.

    A forged or stale `hardware_profile` (the card was disabled when the
    page rendered) is rejected the same way a workflow's own rejected
    choice is: back to the step it came from, with the reason in the
    query string rather than a 500.
    """
    machine = read_machine(settings.data_dir)
    offers = build_profile_offers(machine)
    matching = next((offer for offer in offers if offer.key == hardware_profile), None)
    fields = _carry(hardware_profile, cores_per_chunk, parallel_chunks)
    if matching is None or not matching.fits_free_disk:
        return RedirectResponse(f"{PATH}?{urlencode({**fields, 'error': 'unavailable'})}", 303)
    publish_download_state(
        settings.data_dir, "queued", model_label=weights_for(hardware_profile).label
    )
    job_id = queue.submit_download(hardware_profile)
    write_download_job_id(settings.data_dir, str(job_id))
    if return_to == "/":
        return RedirectResponse("/#vx-first-run", 303)
    return RedirectResponse(f"{PATH}?{urlencode(fields)}", 303)
