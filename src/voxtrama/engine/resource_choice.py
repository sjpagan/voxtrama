"""Checks a run's cores_per_chunk/parallel_chunks against this machine.

Split out of engine.choice_check to keep that module under the project's
file size limit, like engine.diarize_choice.

tuning.core_budget.capped_cores *silently* caps
Settings.cores_per_chunk/.parallel_chunks at what the machine has, because
that number is a machine-wide default nobody asked for by name. A run
choice is a request made by name, so asking for more cores or threads than
exist is refused instead of quietly rewritten to something the caller
never chose (hardware settings are chosen, never detected).
"""

from __future__ import annotations

from voxtrama.config.settings import get_settings
from voxtrama.diagnostics import machine as machine_module
from voxtrama.tuning.core_budget import available_cores
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.rejection import Rejection

_FIELDS = ("cores_per_chunk", "parallel_chunks")


def check_resource_choice(choices: RunChoices) -> list[Rejection]:
    """Reject cores_per_chunk/parallel_chunks the machine cannot give.

    Reads this machine's cores only when one of the two is set: an empty
    RunChoices must not pay for a hardware reading it has no use for.
    Unknown hardware (available is None) caps nothing, for the reason
    tuning.core_budget.capped_cores gives for the same case: a ceiling
    invented from no reading is a guess about the hardware, which is
    never made.
    """
    if choices.cores_per_chunk is None and choices.parallel_chunks is None:
        return []
    machine = machine_module.read_machine(get_settings().data_dir)
    available = available_cores(machine)
    if available is None:
        return []
    asked = (choices.cores_per_chunk, choices.parallel_chunks)
    return [
        Rejection(field, str(value), "this machine", f"available_cores {available}")
        for field, value in zip(_FIELDS, asked, strict=True)
        if value is not None and value > available
    ]
