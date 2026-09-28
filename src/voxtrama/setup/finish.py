"""What POST /setup/private-storage decides before it writes.

Split out of api.routes.setup_storage because that route is already at
the project's 150-line file cap, with no room to also decide what goes into
InstallationConfig. Deciding what to write is not an entrypoint's job
anyway: it only hands the request's values to something that knows the
rules.
"""

from __future__ import annotations

import secrets

from voxtrama.config.settings import Settings
from voxtrama.setup.generative_step import effective_ollama_url, num_ctx_cap_for
from voxtrama.setup.installation import InstallationConfig, read_installation_config
from voxtrama.setup.step_defaults import resolve_step_defaults


def installation_config_from_choices(
    settings: Settings,
    *,
    hardware_profile: str | None,
    cores_per_chunk: int | None,
    parallel_chunks: int | None,
    ollama_model: str | None,
    context_limit: int | None,
) -> InstallationConfig:
    """The file finish_setup writes, built from the choices of steps 1-4.

    A stored token survives a re-run: the guided setup can be revisited
    (no gate stops it), and a second "Finish setup" must not
    invalidate an instance token whose QR or URL may already have
    been shared.

    `ollama_url` is written only when `ollama_model` was. A chosen
    model came from a list some address answered, so that address is
    declared. Without a chosen model there is no proof any address
    answered, and writing one nobody verified is worse than writing none.

    `model_context_limits` is built by `_merged_context_limits`, which
    also re-checks the ceiling of `context_limit`, not trusted from the
    form (see that function's own docstring).
    """
    profile, cores_per_chunk, parallel_chunks = resolve_step_defaults(
        settings, hardware_profile, cores_per_chunk, parallel_chunks
    )
    existing = read_installation_config(settings.data_dir)
    token = existing.instance_token if existing else None
    limits = _merged_context_limits(settings, existing, ollama_model, context_limit)
    return InstallationConfig(
        hardware_profile=profile,
        cores_per_chunk=cores_per_chunk,
        parallel_chunks=parallel_chunks,
        ollama_model=ollama_model,
        model_context_limits=limits,
        ollama_url=effective_ollama_url(settings) if ollama_model else None,
        instance_token=token or secrets.token_urlsafe(32),
        retention_days=existing.retention_days if existing else None,
    )


def _merged_context_limits(
    settings: Settings,
    existing: InstallationConfig | None,
    ollama_model: str | None,
    context_limit: int | None,
) -> dict[str, int]:
    """The file's model_context_limits after this save: what was already
    measured for every other model, plus this call's own entry when there
    is one. A save for `ollama_model` must not erase a ceiling already
    measured for a different model, or picking that model again later
    silently falls back to FALLBACK_MAX_CTX.

    `context_limit`, when given, is clamped to `ollama_model`'s own
    ceiling here, not trusted from the form: `context_limit` only raises
    the field's `max` in the browser, but the model's maximum is read
    again server-side, the same "can only go down" rule the page's copy
    states. The clamped value, not the raw one, is what wins over an
    older entry for the same model.
    """
    limits = dict(existing.model_context_limits) if existing else {}
    if ollama_model and context_limit:
        cap = num_ctx_cap_for(settings, ollama_model)
        limits[ollama_model] = min(context_limit, cap) if cap is not None else context_limit
    return limits
