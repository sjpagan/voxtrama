"""ManifestStep: one row of steps[], the manifest's per-step record.

Split from schema.py to keep that file under the project's file size limit, the
same reason ManifestChoices lives in choices.py and ManifestEvidence in
evidence.py rather than there.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from voxtrama.workflow.skill import Determinism


class ManifestStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str
    skill: str
    skill_version: str
    state: str
    # None only when the skill named by the step cannot be resolved (an
    # unknown skill fails the run before this can be derived): never a
    # value written by hand, always Skill.deterministic.
    deterministic: Determinism | None
    attempts: int
    position: int
    started_at: str | None
    finished_at: str | None
    error: str | None
    # None when started_at or finished_at is missing (a step never
    # started, or still running): zero would claim a duration that has not
    # happened yet (diagnostics/machine.py's own rule for the same shape
    # of gap).
    duration_seconds: float | None
    # The sha256 of what this step produced, in output.json under its own
    # step_id (manifest/output.py). None for a step that produced nothing
    # (skipped, or failed before producing), never an empty string standing
    # in for "nothing". Not to be confused with outputs[].sha256,
    # which hashes the whole file, not one step's share of it.
    output_sha256: str | None
    # The five provenance fields a manifest step carries: which model ran this step, its fingerprint
    # (a pinned weight revision or a provider-reported digest, never the bare tag; None
    # when the weight source itself declares no revision, e.g. diarize's
    # ECAPA-TDNN), where ("local" for an in-process model, a provider name
    # otherwise), which host (None for local: there is none to contact),
    # and whether the profile check was skipped because it could not be
    # verified remotely. All None only for a step whose provenance was
    # never recorded (a step written before migration 0013), never
    # for one the engine ran.
    model: str | None
    model_revision: str | None
    provider: str | None
    host: str | None
    # Boolean, not str | None like the rest: None here means "we do not
    # know" (no provenance ever recorded for this step), False means "the
    # check ran". This is RunStep.profile_check_skipped's distinction,
    # carried through rather than collapsed.
    profile_check_skipped: bool | None
    # What this step consumed: the recording plus every dependency's
    # own output_sha256, never a run id: two runs of the same workflow
    # over the same recording get the same input_sha256. None for a step
    # skipped by its condition, or one written before migration 0015.
    input_sha256: str | None
    # input_sha256 plus which skill ran it, on which hardware
    # profile, with which generative model chosen. It answers "can this
    # output be reused?", not "did my inputs change?" (engine.step_hashing).
    # None for the same two reasons as input_sha256 above.
    reuse_key: str | None
    # The id of the run this step's output was copied from, when it was.
    # Read straight off RunStep.reused_from_run_id, never derived
    # from Run.reused_from_run_id: a run can ask to reuse and still
    # recompute this particular step, when nothing in the source run
    # matched. None for every step that ran, or was skipped.
    reused_from_run_id: str | None
    # The num_ctx a generative call asked
    # Ollama for, whether that number already conceded the estimate did
    # not fit under the model's own ceiling, and how many times the call
    # had to continue past Ollama's own output cap. All three None for a
    # step that never asked a model anything, or one written before
    # migration 0019. Never for a generative step the engine ran.
    context_window_tokens: int | None
    context_window_at_risk: bool | None
    output_resumptions: int | None
    # How many windows the transcript was read in, 1 when it fit
    # whole; None for a step that asked no model anything.
    transcript_windows: int | None = None
