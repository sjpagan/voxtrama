"""voxtrama.toml is born after the first job, from what it used.

Until then the machine's proposal is in force (setup.proposal). When a job
succeeds and there is still no voxtrama.toml, the file is written with the
profile and the two chunking numbers transcription really handed the
model (Transcript.cpu_threads / num_workers), not with what
was proposed: a file that says what ran is worth more than one that says
what was expected. The proposal file is removed, having done its job.

A job that reused an earlier transcript, or ran none, falls back to the
proposal's numbers for what the transcript does not say.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import installation_config_path, proposal_path
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Transcript
from voxtrama.setup.installation import InstallationConfig, write_installation_config
from voxtrama.setup.proposal import proposal_in_force


def settle_after_first_run(session: Session, run_id: str, data_dir: Path) -> bool:
    """Write voxtrama.toml from a first succeeded job; True when it did."""
    if installation_config_path(data_dir).is_file():
        return False
    run = session.get(Run, run_id)
    proposal = proposal_in_force(data_dir)
    if run is None or run.state != RunState.SUCCEEDED or proposal is None:
        return False
    transcript = session.scalars(
        select(Transcript).where(Transcript.produced_by_run_id == run_id)
    ).first()
    used = transcript.hardware_profile if transcript else None
    write_installation_config(
        data_dir,
        InstallationConfig(
            hardware_profile=used if used in ("low", "base", "high") else proposal.hardware_profile,
            cores_per_chunk=(transcript and transcript.cpu_threads) or proposal.cores_per_chunk,
            parallel_chunks=(transcript and transcript.num_workers) or proposal.parallel_chunks,
            instance_token=secrets.token_urlsafe(32),
        ),
    )
    proposal_path(data_dir).unlink(missing_ok=True)
    return True
