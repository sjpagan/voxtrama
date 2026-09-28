"""Diagnostics: what this machine is, and whether Voxtrama can work on it.

Read by `voxtrama doctor`, which measures and advises but
never applies: the profile is chosen by a person, because a detection that
is wrong degrades quality without saying so.

Nothing here formats for a reader (the entrypoint does that),
and nothing here touches the queue: reachability is asked of the queue
adapter by whoever already holds one.

diagnostics.readiness is not re-exported here: it reaches into
transcription.asr for weights_for, and transcription.resources reaches
back into this package for read_machine, so importing readiness at
package level would make `import voxtrama.diagnostics` alone circular
through `voxtrama.transcription`. Every caller already imports it from
voxtrama.diagnostics.readiness directly.
"""

from __future__ import annotations

from voxtrama.diagnostics.advice import advise_profile, warnings
from voxtrama.diagnostics.generative import (
    Fit,
    GenerativeModel,
    GenerativeTable,
    assess_fit,
    load_generative_table,
)
from voxtrama.diagnostics.identity import IdentityReport, read_identity
from voxtrama.diagnostics.machine import MachineReport, read_machine

__all__ = [
    "Fit",
    "GenerativeModel",
    "GenerativeTable",
    "IdentityReport",
    "MachineReport",
    "advise_profile",
    "assess_fit",
    "load_generative_table",
    "read_identity",
    "read_machine",
    "warnings",
]
