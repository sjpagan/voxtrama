"""The shape of a run manifest: Pydantic models only.

writer.py builds and writes these; nothing here reads a database or a
filesystem, so the three issues that will read a manifest
can depend on this file alone.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from voxtrama.manifest.choices import ManifestChoices
from voxtrama.manifest.deletion import ManifestDeletion
from voxtrama.manifest.environment import ManifestEnvironment
from voxtrama.manifest.evidence import ManifestEvidence
from voxtrama.manifest.failure import ManifestFailure
from voxtrama.manifest.step import ManifestStep

# Not a parameter anywhere: bumping it is a deliberate, reviewed change to
# the shape below, never something a caller of writer.py chooses.
#
# 2: adds steps[].duration_seconds and steps[].output_sha256, and later
# steps[].model/.model_revision/.provider/.host/.profile_check_skipped;
# input.source_url and input.source_title; steps[].input_sha256,
# steps[].reuse_key and steps[].reused_from_run_id; steps[].
# context_window_tokens, steps[].context_window_at_risk and steps[].
# output_resumptions; environment.cpu_threads and environment.num_workers;
# run.label and choices.diarize/.max_speakers/.cores_per_chunk/
# .parallel_chunks; steps[].transcript_windows. Manifest is
# extra="forbid", so any new field is a break for an older reader even if
# it is optional, which is why the first bump arrived sooner than it
# looked. All landed against the same version 2, never released, rather
# than bumping once per break.
MANIFEST_VERSION: Literal[2] = 2


class LanguageProvenance(StrEnum):
    """How a language value was decided."""

    USER = "user"
    WORKFLOW = "workflow"
    DEFAULT = "default"
    DETECTED = "detected"
    # None of the four provenances above fits the interface and output
    # languages today, because nothing in the engine resolves those two
    # yet. Guessing one would be an invented field.
    NOT_RECORDED = "not_recorded"


class ManifestDestination(BaseModel):
    """Where a run writes, as a root label plus a path relative to it."""

    model_config = ConfigDict(extra="forbid")
    root: str
    path: str


class ManifestRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    state: str
    # Whether `state` is still going to change. False for as long as the run
    # is pending or running. A reader must not treat a mid-run manifest as
    # the last word on a step it has not reached yet.
    final: bool
    created_at: str
    started_at: str | None
    finished_at: str | None
    destination: ManifestDestination
    # A person's own name for this run, None for one nobody named.
    # See db.models.run.Run.label's own docstring for why it lives on Run,
    # not on Recording, and is never a RunChoices field.
    label: str | None


class ManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recording_id: str
    sha256: str
    duration_seconds: float
    media_format: str
    provenance: str
    # What the source reported about itself when it was fetched: both
    # None for a local file, which has neither. Same name as
    # the Recording column they come from: one name for one fact, so this
    # field has no second name to drift from (ManifestChoices' own reason
    # for not recording the same value twice).
    source_url: str | None
    source_title: str | None


class ManifestLanguage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | None
    provenance: LanguageProvenance


class ManifestLanguages(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interface: ManifestLanguage
    audio: ManifestLanguage
    output: ManifestLanguage


class ManifestWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    # None only when the run failed before resolving a workflow at all (an
    # unknown name, a cyclic graph): there is then no definition to hash.
    definition_sha256: str | None
    local_only_steps: list[str] = []  # Kept local by skill, workflow or step


class ManifestOutput(BaseModel):
    """A file the run produced, hashed so a copy can be told from the original.

    One entry per run today: output.json, the envelope of every step's
    produced value. The shape stays a list, not a single field,
    so the manifest diff and the gold dataset do not have to change the day a run
    starts writing more than one file.
    """

    model_config = ConfigDict(extra="forbid")
    path: str
    sha256: str


class Manifest(BaseModel):
    """How a run was executed. Grows as the run does; `run.final` says when it stops."""

    model_config = ConfigDict(extra="forbid")
    manifest_version: Literal[2] = MANIFEST_VERSION
    run: ManifestRun
    input: ManifestInput | None
    environment: ManifestEnvironment
    languages: ManifestLanguages
    workflow: ManifestWorkflow
    choices: ManifestChoices
    steps: list[ManifestStep]
    outputs: list[ManifestOutput]
    evidence: ManifestEvidence
    failure: ManifestFailure | None
    content_deleted: ManifestDeletion | None = None  # A tombstone
