"""The "Generative models" section of `voxtrama doctor`.

Split out of doctor.py (the project's 150-line file limit) as a separate
context: what this prints depends only on model-catalog/generative.yaml
and a MachineReport, never on the queue, the data directory's identity,
or the hardware profile the rest of doctor.py reports on.

"nobody fits" is a real answer here, printed as such, never
softened into "the smallest one, which almost fits". Reachability, a
provider's version, and measured token rate are left out here:
this asks nothing of a provider, only of the declared table.
"""

from __future__ import annotations

import typer

from voxtrama.diagnostics.advice import GIB
from voxtrama.diagnostics.generative import Fit, assess_fit, load_generative_table
from voxtrama.diagnostics.machine import MachineReport
from voxtrama.workflow.document import DocumentError, DocumentNotFoundError

UNKNOWN = "unknown"


def print_generative(machine: MachineReport) -> None:
    """Report which of the generative model table's entries fit this machine."""
    typer.echo("")
    typer.echo("Generative models")
    typer.echo("  (margin assumes nothing else is loaded, not while transcribing)")
    try:
        table = load_generative_table()
    except (DocumentNotFoundError, DocumentError) as exc:
        typer.echo(f"  the generative model table could not be read: {exc}")
        return
    assessed, reason = assess_fit(table, machine)
    for one in assessed:
        typer.echo(f"  {_fit_line(one)}")
    if reason is None:
        return
    typer.echo(f"  ! {reason}")
    if machine.total_memory_bytes is not None:
        typer.echo("    Use a remote provider, or skip generative steps.")


def _fit_line(fit: Fit) -> str:
    verdict = "fits" if fit.fits else "does not fit"
    margin = f"{fit.margin_bytes / GIB:+.1f} GiB" if fit.margin_bytes is not None else UNKNOWN
    return f"{fit.model.name:<32} {verdict:<11} margin: {margin}"
