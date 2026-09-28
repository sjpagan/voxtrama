"""GET and POST /setup: the writable overview of the settings.
The four-step setup wizard reruns the whole tuning. This is the other half,
the one place that shows what is configured now and lets a single value change
without walking through all four screens again.

Every value shown or offered here comes straight from
setup.installation.read_installation_config, never from
setup.step_defaults.resolve_step_defaults, which proposes a fresh
machine-based guess for whatever a caller leaves out. Pre-filling every
form's hidden fields from the file itself, not from that proposal, is
what keeps "change one value" from silently recomputing every other one
the moment this page's own POST reaches
setup.finish.installation_config_from_choices, the same function
api.routes.setup_storage.finish_setup writes with, reused rather than
rebuilt, so the clamp and the surviving instance_token stay what
that function already guarantees.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import (
    model_row_views,
    profile_options,
    settings_overview_view,
    sidebar_items,
    stored_theme,
    theme_choices,
)
from voxtrama.setup import write_installation_config
from voxtrama.setup.context_cap import resolve_num_ctx_cap
from voxtrama.setup.finish import installation_config_from_choices
from voxtrama.setup.generative_step import model_facts_for, probe_generative_provider
from voxtrama.setup.installation import read_installation_config
from voxtrama.setup.licences import classify_licence

router = APIRouter()

PATH = "/setup"


def _selected_model(requested: str | None, configured: str | None, names: set[str]) -> str | None:
    """The model this render previews: an explicit `?model=` naming one
    Ollama lists, or the one already configured. Never a
    proposal: this page has nothing to propose (see this module's own
    docstring).
    """
    if requested is not None:
        return requested if requested in names else None
    return configured


@router.get(PATH, response_class=HTMLResponse)
def settings_page(
    session: DbDep,
    settings: SettingsDep,
    translator: TranslatorDep,
    model: str | None = None,
) -> HTMLResponse:
    config = read_installation_config(settings.data_dir)
    template = templates_environment.get_template("pages/setup_settings.html")
    context: dict[str, object] = {
        "nav_items": sidebar_items("setup-settings"),
        "configured": config is not None,
        "theme_choices": theme_choices(stored_theme(session)),
        "origin": PATH,
    }
    if config is not None:
        provider = probe_generative_provider(settings)
        facts_by_model = model_facts_for(settings, provider.models)
        licences_by_model = {name: classify_licence(f) for name, f in facts_by_model.items()}
        selected = _selected_model(model, config.ollama_model, {m.name for m in provider.models})
        facts = facts_by_model.get(selected) if selected else None
        context_cap = resolve_num_ctx_cap(facts.context_length) if facts else None
        stored_limit = config.model_context_limits.get(selected) if selected else None
        context.update(
            config=config,
            overview=settings_overview_view(config, settings),
            profile_options=profile_options(),
            provider=provider,
            models=model_row_views(provider.models, licences_by_model),
            selected_model=selected,
            context_cap=context_cap,
            context_limit=stored_limit or context_cap,
        )
    page = page_context(session, translator, settings=settings, **context)
    return HTMLResponse(template.render(**page))


@router.post(PATH)
def save_settings(
    settings: SettingsDep,
    hardware_profile: Annotated[str | None, Form()] = None,
    cores_per_chunk: Annotated[int | None, Form()] = None,
    parallel_chunks: Annotated[int | None, Form()] = None,
    ollama_model: Annotated[str | None, Form()] = None,
    context_limit: Annotated[int | None, Form()] = None,
) -> RedirectResponse:
    """Write one changed value, everything else carried forward by the
    form's own hidden fields (pages/setup_settings.html) rather than
    guessed here (see this module's own docstring on why that matters).
    """
    config = installation_config_from_choices(
        settings,
        hardware_profile=hardware_profile,
        cores_per_chunk=cores_per_chunk,
        parallel_chunks=parallel_chunks,
        ollama_model=ollama_model,
        context_limit=context_limit,
    )
    write_installation_config(settings.data_dir, config)
    return RedirectResponse(PATH, status_code=303)
