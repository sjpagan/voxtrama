"""The machine's proposal, applied and declared before the first job.

No mandatory decision is asked for before the first result, and nothing
is decided for the person in silence. Both hold when the proposal
is applied *and said*: the profile and the two chunking numbers the setup
would have proposed are written to proposal.toml, Settings reads them
(config.installation_source), and the home page shows them with a link to
change them. Nothing here is guessed without being shown.

voxtrama.toml is not written here. It is born after the first job, with
the values that job used (setup.first_run), or earlier if the
person goes through the guided setup. Once it exists the proposal is no
longer in force.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from voxtrama.config.paths import installation_config_path, proposal_path
from voxtrama.config.settings import get_settings
from voxtrama.diagnostics.machine import read_machine
from voxtrama.setup.profile_offers import ProfileOffer, build_profile_offers, recommended_key
from voxtrama.tuning.core_budget import plan_for
from voxtrama.tuning.selector import select_tuning

HEADER = (
    "# What Voxtrama proposed for this machine. In force until the\n"
    "# first job writes voxtrama.toml with the values it actually used, or\n"
    "# until the guided setup (Settings) writes it first.\n\n"
)


@dataclass(frozen=True)
class Proposal:
    hardware_profile: str
    cores_per_chunk: int
    parallel_chunks: int
    offer: ProfileOffer | None = None  # size and cost of the proposed profile


def machine_proposal(data_dir: Path) -> Proposal:
    """What the guided setup would propose on this machine, read now."""
    machine = read_machine(data_dir)
    offers = build_profile_offers(machine)
    key = recommended_key(offers)
    tuning = select_tuning(machine)
    # Asked explicitly so the machine's core count caps them: otherwise
    # a 2-core machine was told "4 cores per chunk" and ran on 2.
    chunking = tuning.chunking
    plan = plan_for(machine, tuning, chunking.cores_per_chunk, chunking.parallel_chunks)
    offer = next((o for o in offers if o.key == key), None)
    return Proposal(key, plan.cores_per_chunk, plan.parallel_chunks, offer)


def _read(path: Path) -> Proposal | None:
    try:
        raw = tomllib.loads(path.read_text())
        return Proposal(
            str(raw["hardware_profile"]), int(raw["cores_per_chunk"]), int(raw["parallel_chunks"])
        )
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError):
        return None


def proposal_in_force(data_dir: Path) -> Proposal | None:
    """The proposal Settings is reading, or None once voxtrama.toml exists."""
    if installation_config_path(data_dir).is_file():
        return None
    return _read(proposal_path(data_dir))


def ensure_proposal(data_dir: Path) -> Proposal | None:
    """Write the proposal once, on a first start; None when voxtrama.toml exists."""
    if installation_config_path(data_dir).is_file():
        return None
    existing = _read(proposal_path(data_dir))
    if existing is not None:
        return existing
    proposal = machine_proposal(data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        proposal_path(data_dir).write_text(
            HEADER
            + f'hardware_profile = "{proposal.hardware_profile}"\n'
            + f"cores_per_chunk = {proposal.cores_per_chunk}\n"
            + f"parallel_chunks = {proposal.parallel_chunks}\n"
        )
    except OSError:  # an unwritable data folder: Settings > Data & privacy says why
        return None
    get_settings.cache_clear()  # same reason as write_installation_config
    return proposal
