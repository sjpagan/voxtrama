"""GET and POST /setup/private-storage: step 4 of the guided setup.

The page shows three facts *verified*, not declared (folder exists, a real write probe via
diagnostics.identity.read_identity, reused rather than rewritten, and free space against the
volume's own total from shutil.disk_usage), then the "Ready to start" summary of what steps 1-3
decided. Its copy reads "Review what you decided before Voxtrama saves this setup", so nothing here
is written on GET: InstallationConfig only exists once "Finish setup" (POST) is pressed.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.setup_nav import setup_breadcrumb, setup_nav_items
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.diagnostics.identity import read_identity as probe_storage
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import (
    disk_usage_view,
    profile_label,
    read_identity,
    setup_step_rows,
    stored_theme,
    theme_choices,
)
from voxtrama.setup import write_installation_config
from voxtrama.setup.finish import installation_config_from_choices
from voxtrama.setup.step_defaults import resolve_step_defaults

router = APIRouter()

PATH = "/setup/private-storage"


def _disk_usage(data_dir: Path) -> tuple[int, int, int] | None:
    """(total, used, free) bytes on `data_dir`'s volume, or None if unreadable."""
    try:
        usage = shutil.disk_usage(data_dir)
    except OSError:
        return None
    return usage.total, usage.used, usage.free


def _carry(hardware_profile: str, cores_per_chunk: int, parallel_chunks: int) -> dict[str, object]:
    return {
        "hardware_profile": hardware_profile,
        "cores_per_chunk": cores_per_chunk,
        "parallel_chunks": parallel_chunks,
    }


@router.get(PATH, response_class=HTMLResponse)
def private_storage_page(
    session: DbDep,
    settings: SettingsDep,
    translator: TranslatorDep,
    hardware_profile: str | None = None,
    cores_per_chunk: int | None = None,
    parallel_chunks: int | None = None,
    ollama_model: str | None = None,
    context_limit: int | None = None,
) -> HTMLResponse:
    write_probe = probe_storage(settings.data_dir)
    usage = _disk_usage(settings.data_dir) if write_probe.data_dir_exists else None
    # Resolve first, then pass to the sidebar: Setup's
    # sub-entries carry the resolved values, not the ones received.
    hardware_profile, cores_per_chunk, parallel_chunks = resolve_step_defaults(
        settings, hardware_profile, cores_per_chunk, parallel_chunks
    )
    identity = read_identity(session)
    fields = _carry(hardware_profile, cores_per_chunk, parallel_chunks)
    template = templates_environment.get_template("pages/setup_private_storage.html")
    return HTMLResponse(
        template.render(
            **page_context(
                session,
                translator,
                settings=settings,
                nav_items=setup_nav_items("setup-storage", fields),
                wizard_steps=setup_step_rows("storage"),
                # The folder as the host machine knows it (compose.yaml's
                # own VOXTRAMA_HOST_DATA_DIR), never the container's `/data`
                # mount point, which is all settings.data_dir holds in there.
                data_dir=settings.host_data_dir or str(settings.data_dir),
                write_probe=write_probe,
                usage=disk_usage_view(usage),
                person_name=identity.full_name if identity else None,
                profile_label=profile_label(hardware_profile),
                parallelism_label=f"{parallel_chunks} chunks × {cores_per_chunk} cores",
                ollama_model=ollama_model,
                hardware_profile=hardware_profile,
                cores_per_chunk=cores_per_chunk,
                parallel_chunks=parallel_chunks,
                context_limit=context_limit,
                theme_choices=theme_choices(stored_theme(session)),
                origin=PATH,
                breadcrumb=setup_breadcrumb("setup-storage"),
            )
        )
    )


@router.post(PATH)
def finish_setup(
    settings: SettingsDep,
    hardware_profile: Annotated[str | None, Form()] = None,
    cores_per_chunk: Annotated[int | None, Form()] = None,
    parallel_chunks: Annotated[int | None, Form()] = None,
    ollama_model: Annotated[str | None, Form()] = None,
    context_limit: Annotated[int | None, Form()] = None,
) -> RedirectResponse:
    """Write the installation's own file, then land on the home page.

    The token, clamp and Ollama-address rules for that file live in
    setup.finish.installation_config_from_choices. This route only carries
    the form's own values there and writes what comes back.
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
    return RedirectResponse("/", status_code=303)
