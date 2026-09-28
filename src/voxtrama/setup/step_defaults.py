"""The guided setup's defaults for hardware_profile/cores_per_chunk/parallel_chunks,
when a step 3 or 4 request arrives without them.

A parameter missing from the query string means "nobody decided yet". The answer is not a
constant chosen because it is low, but the
proposal step 2's GET already shows: the machine
(diagnostics.machine), the tuning file it selects (tuning.selector), the recommended
profile (setup.profile_offers) and the core budget (tuning.core_budget.plan_for). A value
given explicitly still wins, capped at the cores that exist (untouched here).

The POST that finishes the setup (api.routes.setup_storage.finish_setup) resolves through
here too, and there it matters most: that function *writes* the installation file. The
GET's form always carries the three resolved values, so the ordinary path never arrives
empty-handed. Still, what lands on disk cannot default to a machine nobody has just
because arriving without them is rare.
"""

from __future__ import annotations

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.machine import read_machine
from voxtrama.setup.profile_offers import PROFILE_KEYS, build_profile_offers, recommended_key
from voxtrama.tuning.core_budget import plan_for
from voxtrama.tuning.selector import select_tuning


def resolve_step_defaults(
    settings: Settings,
    hardware_profile: str | None,
    cores_per_chunk: int | None,
    parallel_chunks: int | None,
) -> tuple[str, int, int]:
    """`hardware_profile`/`cores_per_chunk`/`parallel_chunks` as given, or this machine's
    proposal for whichever of the three is missing.
    """
    machine = read_machine(settings.data_dir)
    tuning = select_tuning(machine)
    offers = build_profile_offers(machine)
    profile = hardware_profile if hardware_profile in PROFILE_KEYS else recommended_key(offers)
    plan = plan_for(machine, tuning, cores_per_chunk, parallel_chunks)
    return profile, plan.cores_per_chunk, plan.parallel_chunks
