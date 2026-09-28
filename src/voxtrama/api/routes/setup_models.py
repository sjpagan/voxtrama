"""GET /setup/model-ready: step 3 of the guided setup.

The page shows the configured Ollama's own models
(setup.generative_step.probe_generative_provider, the same call `doctor`
makes), the tuning file's own generative.memory sentence formatted with
this machine's real reading, each model's own licence per row
(setup.generative_step.model_facts_for + setup.licences), and the
num_ctx ceiling for whichever model is selected, reused from the same
facts, not read a second time.

With no `model=` in the query string, the first installed model with a
permissive licence is preselected (`_select_model` below); an explicit
`model=` always wins, permissive or not.

No POST here: this step writes nothing to disk or to the database. It
only reads and offers a choice forward. Clicking a model row is a real
navigation (a link carrying `model=` in the query string) rather than a
script flipping state, because picking a different model needs a fresh
/api/show call, and only a request can make one (no JavaScript).
If Ollama does not answer, the wizard proceeds: "Skip" and "Continue"
both lead to step 4, the
first with no generative model carried forward, the second with the number-of-tokens
field this page itself renders.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.setup_nav import setup_breadcrumb, setup_nav_items
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.diagnostics.machine import MachineReport, read_machine
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.providers.probe import ProviderModel
from voxtrama.rendering import model_row_views, setup_step_rows, stored_theme, theme_choices
from voxtrama.setup.context_cap import resolve_num_ctx_cap
from voxtrama.setup.generative_step import model_facts_for, probe_generative_provider
from voxtrama.setup.licences import ModelLicence, classify_licence, first_permissive_model
from voxtrama.setup.step_defaults import resolve_step_defaults
from voxtrama.tuning.definition import TuningFile
from voxtrama.tuning.selector import select_tuning

router = APIRouter()

PATH = "/setup/model-ready"
STORAGE_PATH = "/setup/private-storage"
GIB = 1024**3


def _memory_notice(machine: MachineReport, tuning: TuningFile) -> str | None:
    """The tuning file's own sentence (tuning/*.yaml), formatted with a real reading.

    Shown regardless of whether this machine falls short (the amber box
    reads the same way on a 36 GiB Mac well above its 16 GiB
    recommendation), so no comparison happens here, only the
    formatting diagnostics.machine's own "unknown, never a plausible
    number" rule allows when the reading exists.
    """
    if machine.total_memory_bytes is None:
        return None
    return tuning.generative.memory.warning.format(
        recommended_gib=tuning.generative.memory.recommended_gib,
        actual_gib=round(machine.total_memory_bytes / GIB),
    )


def _select_model(
    requested: str | None,
    models: tuple[ProviderModel, ...],
    licences_by_model: dict[str, ModelLicence],
) -> str | None:
    """Which model is selected: an explicit `model=` wins outright, even
    an unrecognised or constrained one (recommended, not prevented). Only
    its absence triggers the proposal, the first installed model with a
    permissive licence (or none, if none qualify).
    An explicit `model=` naming something not installed selects nothing.
    """
    if requested is not None:
        return requested if requested in {m.name for m in models} else None
    return first_permissive_model(models, licences_by_model)


@router.get(PATH, response_class=HTMLResponse)
def model_ready_page(
    session: DbDep,
    settings: SettingsDep,
    translator: TranslatorDep,
    hardware_profile: str | None = None,
    cores_per_chunk: int | None = None,
    parallel_chunks: int | None = None,
    model: str | None = None,
) -> HTMLResponse:
    machine = read_machine(settings.data_dir)
    tuning = select_tuning(machine)
    hardware_profile, cores_per_chunk, parallel_chunks = resolve_step_defaults(
        settings, hardware_profile, cores_per_chunk, parallel_chunks
    )
    provider = probe_generative_provider(settings)
    facts_by_model = model_facts_for(settings, provider.models)
    licences_by_model = {name: classify_licence(facts) for name, facts in facts_by_model.items()}
    selected = _select_model(model, provider.models, licences_by_model)
    facts = facts_by_model.get(selected) if selected else None
    context_cap = resolve_num_ctx_cap(facts.context_length) if facts else None
    fields = {
        "hardware_profile": hardware_profile,
        "cores_per_chunk": cores_per_chunk,
        "parallel_chunks": parallel_chunks,
    }
    template = templates_environment.get_template("pages/setup_model_ready.html")
    return HTMLResponse(
        template.render(
            **page_context(
                session,
                translator,
                settings=settings,
                nav_items=setup_nav_items("setup-model", fields),
                wizard_steps=setup_step_rows("models"),
                provider=provider,
                models=model_row_views(provider.models, licences_by_model),
                selected_model=selected,
                context_cap=context_cap,
                memory_notice=_memory_notice(machine, tuning),
                hardware_profile=hardware_profile,
                cores_per_chunk=cores_per_chunk,
                parallel_chunks=parallel_chunks,
                storage_path=STORAGE_PATH,
                theme_choices=theme_choices(stored_theme(session)),
                origin=PATH,
                breadcrumb=setup_breadcrumb("setup-model"),
            )
        )
    )
