"""GET /models: the permanent library of every model this installation
manages: Transcription's three Whisper profiles, Speakers' own
ECAPA-TDNN, and a read-only look at whatever the configured Ollama
exposes, plus the one line at the top saying what this installation
uses (setup.installation.read_installation_config).

Downloading and removing weights already exist for the guided setup's
own step 2 (api.routes.setup_processing, api.routes.setup_model_remove).
api.routes.models_download and api.routes.models_actions reuse the same
core calls (publish_download_state, queue.submit_download,
remove_weights) through two thin POSTs of their own, rather than a
`return_to` field carried back into the wizard's own routes: this page
never has to trust a value from the form for where to send someone next,
since it only ever sends them back here. `weight_set_for` and
LIBRARY_KEYS live here because both of those POSTs need the same lookup
this GET already builds every row from.

ECAPA-TDNN was this project's real gap: it downloads in silence
on a run's first diarize step, nobody has ever seen its licence or its
size, and nobody could remove it. queue.submit_download and
worker.tasks.download_model_job were widened to accept its own key
(weights.ECAPA_KEY) alongside the three hardware profiles, never made
to pretend it is a fourth one, since a profile is a choice and ECAPA is
not.

This GET used to hide the row's own actions while `downloading`
and say nothing else. A multi-gigabyte download running silent is
a fault: an unannounced wait. The fix reuses step 2's own
machinery rather than inventing a second one: `rendering.download_view`
turns the same `ProgressState` into the bar and byte counts
pages/models.html now shows on the row whose label matches
`download.model_label`, and the template polls with the same plain
`<meta http-equiv="refresh">` while `downloading` is true. `DOWNLOAD_SLOT`
is one slot for the whole installation (setup.download_progress), so a
download started from step 2 shows up here too, and vice versa: the
same `read_download_state` call, not a second channel.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.config.settings import Settings
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import (
    WeightRowView,
    download_view,
    installation_summary_view,
    model_row_views,
    sidebar_items,
    stored_theme,
    theme_choices,
    weight_row,
)
from voxtrama.setup import IN_PROGRESS_STATES, read_download_state
from voxtrama.setup.generative_step import model_facts_for, probe_generative_provider
from voxtrama.setup.installation import read_installation_config
from voxtrama.setup.licences import classify_licence
from voxtrama.setup.profile_offers import PROFILE_KEYS
from voxtrama.transcription.asr import weights_for
from voxtrama.weights import ECAPA_KEY, WeightSet, ecapa_weights, is_cached

router = APIRouter()

PATH = "/models"
DOWNLOAD_PATH = f"{PATH}/download"
REMOVE_PATH = f"{PATH}/remove"

# The four rows the library shows, in the order Transcription then
# Speakers draws them. Generative is a fourth group, but a read-only one
# with no key of its own to download or remove (Voxtrama does not
# run `ollama pull`).
LIBRARY_KEYS = (*PROFILE_KEYS, ECAPA_KEY)


def weight_set_for(key: str) -> WeightSet:
    """The WeightSet behind one library key: worker.tasks._weight_set_for's
    own two-branch rule, read again here because building each row and
    handling each POST both need it before any job is ever enqueued.
    """
    return ecapa_weights() if key == ECAPA_KEY else weights_for(key)


def _weight_rows(settings: Settings, active_profile: str | None) -> list[WeightRowView]:
    """One row per LIBRARY_KEYS entry: Transcription's three profiles,
    then Speakers' own ECAPA-TDNN.
    """
    rows = []
    for key in LIBRARY_KEYS:
        weights = weight_set_for(key)
        installed = is_cached(weights, settings.models_dir)
        active = key == ECAPA_KEY or key == active_profile
        rows.append(
            weight_row(key, weights, installed=installed, redownload_notice=installed and active)
        )
    return rows


@router.get(PATH, response_class=HTMLResponse)
def models_page(session: DbDep, settings: SettingsDep, translator: TranslatorDep) -> HTMLResponse:
    config = read_installation_config(settings.data_dir)
    state = read_download_state(settings.data_dir)
    downloading = state is not None and state.state in IN_PROGRESS_STATES
    rows = _weight_rows(settings, config.hardware_profile if config else None)

    provider = probe_generative_provider(settings)
    facts_by_model = model_facts_for(settings, provider.models)
    licences_by_model = {name: classify_licence(facts) for name, facts in facts_by_model.items()}

    template = templates_environment.get_template("pages/models.html")
    return HTMLResponse(
        template.render(
            **page_context(
                session,
                translator,
                settings=settings,
                nav_items=sidebar_items("models"),
                summary=installation_summary_view(config),
                transcription_rows=rows[:-1],
                speaker_row=rows[-1],
                provider=provider,
                generative_models=model_row_views(provider.models, licences_by_model),
                downloading=downloading,
                download=download_view(state) if state is not None else None,
                download_path=DOWNLOAD_PATH,
                remove_path=REMOVE_PATH,
                theme_choices=theme_choices(stored_theme(session)),
                origin=PATH,
            )
        )
    )
