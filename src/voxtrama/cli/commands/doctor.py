"""The `voxtrama doctor` command: measure this installation, advise, never apply.

This command has two jobs that pull in opposite directions. It
is the first thing a newcomer runs, so it has to be readable. It is also
what we ask for when someone opens a report, so it has to be complete and
honest: "a diagnostic that always says everything is fine stops being
read".

It suggests a hardware profile and prints the line that would apply it,
but writes nothing: that choice stays with the person, because a
detection that guesses wrong makes a setting look like a slow product.
"""

from __future__ import annotations

from typing import Annotated

import typer

from voxtrama.cli.commands.doctor_generative import print_generative
from voxtrama.cli.commands.doctor_provider import print_provider
from voxtrama.config.settings import Settings, get_settings
from voxtrama.diagnostics import advise_profile, read_identity, read_machine, warnings
from voxtrama.diagnostics.identity import IdentityReport
from voxtrama.diagnostics.machine import MachineReport
from voxtrama.humanize import human_bytes
from voxtrama.queue.errors import QueueUnavailable
from voxtrama.queue.rq_backend import RQBackend

UNKNOWN = "unknown"


def doctor_command(
    no_measure: Annotated[
        bool, typer.Option("--no-measure", help="Skip timing a real generation on the provider.")
    ] = False,
) -> None:
    """Report what this machine offers, what Voxtrama can reach, and what to set."""
    settings = get_settings()
    machine = read_machine(settings.data_dir)
    identity = read_identity(settings.data_dir)

    _print_machine(machine)
    _print_storage(settings, identity, machine)
    _print_queue(settings)
    _print_advice(machine, settings)
    print_generative(machine)
    print_provider(settings, measure=not no_measure)

    if not identity.write_ok:
        raise typer.Exit(code=1)


def _print_machine(machine: MachineReport) -> None:
    memory = human_bytes(machine.total_memory_bytes) if machine.total_memory_bytes else UNKNOWN
    typer.echo("Machine")
    where = " (in a container)" if machine.in_container else ""
    typer.echo(f"  platform:     {machine.platform} / {machine.architecture}{where}")
    typer.echo(f"  CPU:          {machine.cpu_brand or UNKNOWN}")
    typer.echo(f"  CPU cores:    {_cores_line(machine)}")
    unified = " (unified with GPU)" if machine.unified_memory else ""
    typer.echo(f"  memory:       {memory}{unified}")
    typer.echo(f"  accelerator:  {machine.accelerator or 'none detected'}")


def _cores_line(machine: MachineReport) -> str:
    """Performance/efficiency split where the platform reports one, a single count otherwise."""
    if machine.performance_cores is not None and machine.efficiency_cores is not None:
        return f"{machine.performance_cores} performance + {machine.efficiency_cores} efficiency"
    return str(machine.cpu_count) if machine.cpu_count is not None else UNKNOWN


def _print_storage(settings: Settings, identity: IdentityReport, machine: MachineReport) -> None:
    free = machine.free_disk_bytes
    typer.echo("")
    typer.echo("Data directory")
    typer.echo(f"  path:         {settings.data_dir}")
    typer.echo(f"  exists:       {'yes' if identity.data_dir_exists else 'no'}")
    typer.echo(f"  free space:   {human_bytes(free) if free else UNKNOWN}")
    typer.echo(f"  process uid:  {_ids(identity.process_uid, identity.process_gid)}")
    typer.echo(f"  owned by:     {_ids(identity.data_dir_uid, identity.data_dir_gid)}")
    _print_write_probe(settings, identity)


def _print_write_probe(settings: Settings, identity: IdentityReport) -> None:
    """Report the write probe, and how to fix it when it failed.

    The proof is a real file created and removed (diagnostics.identity):
    matching uid numbers are not evidence on a bind mount, a network
    share or a remapped user namespace.
    """
    if identity.write_ok:
        typer.echo("  write test:   ok (a file was created and removed)")
        return
    typer.echo(f"  write test:   FAILED: {identity.write_error}")
    if not identity.data_dir_exists:
        typer.echo(f"    {settings.data_dir} does not exist. Create it, or point")
        typer.echo("    VOXTRAMA_DATA_DIR at a folder that does.")
        return
    typer.echo("    The process cannot write where its data must go. Either make the")
    typer.echo(f"    folder writable by uid {identity.process_uid}, or set VOXTRAMA_RUN_AS_UID")
    typer.echo(f"    to {identity.data_dir_uid} in .env and restart.")


def _print_queue(settings: Settings) -> None:
    typer.echo("")
    typer.echo("Queue")
    typer.echo(f"  url:          {settings.queue_url}")
    try:
        RQBackend(settings.queue_url).ping()
    except QueueUnavailable as exc:
        typer.echo(f"  reachable:    NO: {exc}")
        typer.echo("    Start it with `docker compose up redis`, or point")
        typer.echo("    VOXTRAMA_QUEUE_URL at a Redis that is already running.")
        return
    typer.echo("  reachable:    yes")


def _print_advice(machine: MachineReport, settings: Settings) -> None:
    """Print the warnings, then the suggested profile and the line that sets it."""
    typer.echo("")
    for warning in warnings(machine):
        typer.echo(f"  ! {warning}")

    suggested, reason = advise_profile(machine)
    typer.echo("Hardware profile")
    typer.echo(f"  configured:   {settings.hardware_profile}")
    if suggested is None:
        typer.echo(f"  suggested:    none: {reason}")
        return
    typer.echo(f"  suggested:    {suggested}: {reason}")
    if suggested == settings.hardware_profile:
        return
    typer.echo("")
    typer.echo("  To use the suggestion, put this line in .env and restart:")
    typer.echo(f"    VOXTRAMA_HARDWARE_PROFILE={suggested}")
    typer.echo("  Nothing here changes it for you: the choice is yours.")


def _ids(uid: int | None, gid: int | None) -> str:
    if uid is None:
        return UNKNOWN
    return f"{uid}:{gid}"
