"""The "Generative provider" section of `voxtrama doctor`.

Split out of doctor.py (150 lines/file) as a separate context:
this talks to a remote provider over HTTP, while the rest of doctor.py
reads the local machine and the queue. Split from doctor_generative.py
for the same reason: that section asks a declared table whether a model
fits in memory. This asks the provider itself, and can fail in ways a
table read never does.
"""

from __future__ import annotations

import typer

from voxtrama.config.settings import Settings
from voxtrama.humanize import human_bytes
from voxtrama.providers.base import ProviderError
from voxtrama.providers.ollama import OllamaProvider, classify_host
from voxtrama.providers.probe import GenerationSpeed, ProviderModel, ProviderProbe
from voxtrama.providers.registry import NamedProvider, configured_providers
from voxtrama.providers.version import MINIMUM_VERSION, meets_minimum

UNKNOWN = "unknown"


def print_provider(settings: Settings, *, measure: bool) -> None:
    """Report every configured generative provider: where, local or remote, what it has."""
    typer.echo("")
    typer.echo("Generative provider")
    providers = configured_providers(settings)
    if not providers:
        _print_not_configured()
        return
    for provider in providers.values():
        _print_one(settings, provider, measure=measure)


def _print_one(settings: Settings, named: NamedProvider, *, measure: bool) -> None:
    host, _ = classify_host(named.url)
    typer.echo(f"  name:         {named.name} ({named.locality})")
    typer.echo(f"  host:         {host}")
    auth = named.auth.get_secret_value() if named.auth else None
    provider = OllamaProvider(named.url, auth, settings.provider_timeout_seconds)
    probe = provider.probe()
    _print_reachability(probe)
    if not probe.reachable:
        return
    _print_version(probe.version)
    _print_models(probe.models)
    if not measure:
        typer.echo("  speed:        skipped (--no-measure)")
        return
    _print_speed(provider, probe.models)


def _print_not_configured() -> None:
    """Same register as doctor.py's Hardware profile: suggest a line, never write one."""
    typer.echo("  configured:   no generative provider is configured")
    typer.echo("")
    typer.echo("  To use one, put a line like this in .env and restart:")
    typer.echo("    VOXTRAMA_OLLAMA_URL=http://localhost:11434")
    typer.echo("  (add VOXTRAMA_OLLAMA_AUTH too if that server needs credentials;")
    typer.echo('  several servers, by name: VOXTRAMA_PROVIDERS=\'{"box": {"url": "..."}}\'.)')


def _print_reachability(probe: ProviderProbe) -> None:
    """Same tone as doctor.py's Queue section: say the guess, not raise it."""
    if not probe.reachable:
        typer.echo(f"  reachable:    NO: {probe.error}")
        return
    latency = (
        f"{probe.latency_seconds * 1000:.0f} ms" if probe.latency_seconds is not None else UNKNOWN
    )
    typer.echo(f"  reachable:    yes (latency: {latency})")


def _print_version(version: str | None) -> None:
    if version is None:
        typer.echo("  version:      unknown: the provider did not declare one")
        return
    verdict = meets_minimum(version, MINIMUM_VERSION)
    if verdict is None:
        typer.echo(
            f"  version:      {version} (cannot be compared to our minimum {MINIMUM_VERSION})"
        )
    elif verdict:
        typer.echo(f"  version:      {version} (meets our minimum {MINIMUM_VERSION})")
    else:
        typer.echo(f"  version:      {version} (does NOT meet our minimum {MINIMUM_VERSION})")


def _print_models(models: tuple[ProviderModel, ...]) -> None:
    if not models:
        typer.echo("  models:       none present")
        return
    typer.echo("  models:")
    for model in models:
        size = human_bytes(model.size_bytes) if model.size_bytes is not None else UNKNOWN
        typer.echo(f"    {model.name:<20} {size}")


def _smallest_model(models: tuple[ProviderModel, ...]) -> ProviderModel | None:
    """The model doctor will time: the smallest by declared size, size known.

    Measuring the largest could cost minutes doctor should not spend
    uninvited. A model whose size is unknown (size_bytes None) cannot be
    compared, so it is excluded instead of assumed smallest.
    """
    sized = [model for model in models if model.size_bytes is not None]
    return min(sized, key=lambda model: model.size_bytes) if sized else None


def _print_speed(provider: OllamaProvider, models: tuple[ProviderModel, ...]) -> None:
    smallest = _smallest_model(models)
    if smallest is None:
        typer.echo("  speed:        not measured: no model reports a size to compare")
        return
    typer.echo(f"  speed:        measuring on {smallest.name} (the smallest present)...")
    try:
        speed = provider.measure_generation(smallest.name)
    except ProviderError as exc:
        typer.echo(f"  speed:        FAILED: {exc}")
        return
    _print_speed_result(speed)


def _print_speed_result(speed: GenerationSpeed) -> None:
    load = f"{speed.load_seconds:.1f} s" if speed.load_seconds is not None else UNKNOWN
    typer.echo(f"  model load:   {load}")
    if speed.tokens_per_second is None:
        typer.echo(
            f"  generation:   rate unknown ({speed.source}), {speed.wall_seconds:.1f} s wall clock"
        )
        return
    typer.echo(
        f"  generation:   {speed.tokens_per_second:.1f} tokens/s over {speed.tokens} tokens "
        f"({speed.source}, model load shown above)"
    )
