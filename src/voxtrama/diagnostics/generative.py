"""Whether a generative model fits on this machine, before we ever call one.

"nobody" is a legitimate answer, and doctor.py has to be able
to give it without pretending otherwise. This module only measures fit
against declared memory (model-catalog/generative.yaml); reachability,
latency and a provider's version are checked elsewhere
(see providers/base.TextProvider, which this module does not touch).

No I/O here beyond reading the table itself: fits() and assess_fit() are
pure functions of a GenerativeModel/GenerativeTable and a MachineReport,
the same split advice.py already uses between reading a machine and
reasoning about it.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from voxtrama.diagnostics.advice import GIB
from voxtrama.diagnostics.machine import MachineReport
from voxtrama.workflow.document import find_document, read_document

# What the OS and Voxtrama's process hold before a model gets a single
# byte, on the machine the model would run on (the rule "we don't
# know what a remote provider's machine is already serving" does not apply
# here: this is the local node only). Declared once, like
# required_memory_gib, instead of measured per machine: "fits exactly" is
# the case this catches, so a model whose declared weight equals total
# memory must still come back as not fitting.
#
# It does NOT cover a workflow already holding other weights in memory.
# transcribe-then-summarize has the ASR weights (~1.5 GB, next to
# advice.COMFORTABLE_FREE_DISK_BYTES) resident by the time a generative
# step runs, and this reservation ignores that: the margin below assumes
# a machine that is not transcribing at the same moment. A number for
# "whichever workflow happens to run first" would be the invented
# threshold ("soglia inventata") the project already rejects.
RESERVED_MEMORY_BYTES = 2 * GIB


class GenerativeModel(BaseModel):
    """One entry of model-catalog/generative.yaml: a model this table can advise on.

    required_memory_gib is declared, not derived from parameters_b and
    quantization: that would mean inventing the KV cache and context
    length, two numbers nobody has measured (an invented threshold,
    "soglia inventata"). Declaring it also lets someone editing their own
    copy of the table change it without touching code.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    parameters_b: float
    active_parameters_b: float | None = None
    quantization: str
    required_memory_gib: float
    note: str | None = None


class GenerativeTable(BaseModel):
    """model-catalog/generative.yaml itself: a version, and the models it lists."""

    model_config = ConfigDict(extra="forbid")

    version: int
    models: list[GenerativeModel]


@dataclass(frozen=True)
class Fit:
    """One model checked against one machine: whether it fits, and by how much.

    margin_bytes is the number a diagnostic has to carry
    alongside its verdict. It stays None when the machine's memory could
    not be read, never a 0 that would read as "fits exactly".
    """

    model: GenerativeModel
    fits: bool
    margin_bytes: int | None


def fits(model: GenerativeModel, machine: MachineReport) -> Fit:
    """`model` against `machine`, reserving RESERVED_MEMORY_BYTES for the OS and Voxtrama.

    Declines to decide when memory could not be read: no model declares
    itself a fit on a reading that does not exist, just as
    advise_profile refuses to suggest a profile in the same case.
    """
    memory = machine.total_memory_bytes
    if memory is None:
        return Fit(model=model, fits=False, margin_bytes=None)
    required = int(model.required_memory_gib * GIB)
    margin = memory - required - RESERVED_MEMORY_BYTES
    return Fit(model=model, fits=margin > 0, margin_bytes=margin)


def assess_fit(table: GenerativeTable, machine: MachineReport) -> tuple[list[Fit], str | None]:
    """Every model in `table`, in file order, plus a reason when none of them fits.

    Never sorted by margin or by verdict: the order is the file's, because
    a list sorted by fit would read as a ranking. Ranking generative
    models is for later work to make possible one day, not a side
    effect of `doctor`.
    """
    assessed = [fits(model, machine) for model in table.models]
    if machine.total_memory_bytes is None:
        return assessed, "memory could not be read on this platform, so no model is assessed"
    if not any(one.fits for one in assessed):
        # Never names a path here: the table read could be the shipped one
        # or a user's own override in $VOXTRAMA_DATA_DIR/model-catalog
        # (load_generative_table), and this function does not know which
        # one won. Naming the wrong one would be worse than naming none.
        return assessed, "no model in the generative model table fits in this machine's memory"
    return assessed, None


def load_generative_table() -> GenerativeTable:
    """Read model-catalog/generative.yaml, following the same two roots as workflows and skills.

    The same rule applies unmodified: a copy in
    $VOXTRAMA_DATA_DIR/model-catalog wins over the one the package ships, so
    trying another combination of models needs no release.
    """
    path = find_document("model-catalog", "generative", "generative model table")
    return read_document(path, GenerativeTable)
