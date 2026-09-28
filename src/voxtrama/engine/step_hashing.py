"""What a step consumed (input_sha256), and whether its output can be reused (reuse_key).

engine.preparation.execute_step calls both, on every step, right before
invoking the step's implementation: the one moment the step's
dependencies have produced and this step has not yet run. Neither value
is used to skip anything here. This
module only records a truth the engine did not write down before.

manifest never imports engine (see manifest/evidence.py's docstring and
tests/test_architecture.py), so the reverse direction is the only one
available: this lives in engine and imports manifest.jsonfile.serialize and
manifest.output.step_output_hash, the same stable serialization
steps[].output_sha256 is already hashed with.
"""

from __future__ import annotations

import hashlib

from voxtrama.db.models.step import RunStep
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.progress import write_step_hashes
from voxtrama.manifest.jsonfile import serialize
from voxtrama.manifest.output import step_output_hash
from voxtrama.workflow.definition import Step

# The two extractive skills: neither reads the declared context
# in a way a regenerated job should redo them for.
_NOT_GENERATIVE = frozenset({"transcribe", "diarize"})


def input_sha256(step: Step, context: ExecutionContext) -> str:
    """sha256 of what `step` consumes: the recording plus every dependency's output.

    `recording_sha256` enters every step, not only ones with no
    `depends_on`. The alternative (a skill declaring which roots it reads,
    since e.g. diarize reads `ctx.audio_path` as well as transcribe's
    output) has nothing here to validate that declaration against, and a
    declaration that never fails silently drifts from what the skill
    does. Treating every step as depending on the whole recording is
    always true, and trusts no skill's claim about itself.

    A dependency that produced nothing (skipped, or failed before
    producing) maps to step_output_hash's None. That None is kept in
    `depends_on` instead of dropped: it is a fact about what happened, and
    omitting the key would make "no entry" and "entry is None" the same
    thing to a reader, when they are not.

    No run id, row id or timestamp enters this hash. Reuse depends
    entirely on that. Two runs of the same workflow over the same recording must
    hash identically, or no comparison of two runs' input_sha256 means
    anything.
    """
    recording_sha256 = context.recording.content_sha256 if context.recording is not None else None
    payload = {
        "recording_sha256": recording_sha256,
        "depends_on": {dep: step_output_hash(dep, context.produced) for dep in step.depends_on},
    }
    return hashlib.sha256(serialize(payload)).hexdigest()


def reuse_key(step: Step, context: ExecutionContext) -> str:
    """sha256 of input_sha256 plus the identity of whoever would reuse its output.

    `step.skill`/`step.skill_version` are read here after
    engine.preparation._apply_step_choices has already substituted a run's
    chosen skill for the workflow's declared one, so they are what ran.
    `choices.step_skills` is deliberately left out of this hash: it is the
    source _apply_step_choices consumed to produce
    `step.skill`/`step.skill_version`, and folding it in again would count
    the same choice twice under two names.

    Neither `skill_version` nor these two choices enter input_sha256
    above: that hash answers "did what I depend on change?", and none of
    the three change what was fed in, only what will run on it. Putting
    them there would make retouching a workflow mark half the archive
    `stale`, an invalidation that must not happen.
    """
    payload = {
        "input_sha256": input_sha256(step, context),
        "skill": step.skill,
        "skill_version": step.skill_version,
        "hardware_profile": context.choices.hardware_profile,
        "generative_model": context.choices.generative_model,
    }
    payload.update(_choices_read_by(step, context))
    return hashlib.sha256(serialize(payload)).hexdigest()


def _choices_read_by(step: Step, context: ExecutionContext) -> dict[str, object]:
    """The run's choices, only for the step that reads each and only when made.

    The declared context steers every generative step, the detail steers
    summarize. A job regenerated with either changed must not adopt
    that step's old output. Transcription keeps its own when only the
    context changes: a corrected context
    changes the next results, not the transcript already made. Left out
    when unset, so every key computed before these choices existed stays
    the same.
    """
    extra: dict[str, object] = {}
    if step.skill not in _NOT_GENERATIVE and context.choices.context:
        extra["context"] = context.choices.context
    if step.skill not in _NOT_GENERATIVE and context.choices.output_language:
        extra["output_language"] = context.choices.output_language
    if step.skill not in _NOT_GENERATIVE and context.choices.provider:
        extra["provider"] = context.choices.provider  # Another server, another run
    if getattr(step, "instructions", None):  # other instructions, another output
        extra["instructions"] = hashlib.sha256(step.instructions.encode()).hexdigest()
    if step.id in context.kept_local:
        extra["kept_local"] = context.kept_local[step.id]  # Never adopt what went out
    if step.skill == "summarize" and context.choices.summary_detail is not None:
        extra["summary_detail"] = context.choices.summary_detail
    return extra


def record_step_hashes(context: ExecutionContext, step: Step, row: RunStep) -> None:
    """Compute both values and persist them on `row`, right before `step` runs.

    The single entry point engine.preparation.execute_step calls: every
    dependency of `step` has already produced by the time this runs, and
    `step` has not, which is the pair of facts input_sha256 and reuse_key
    need. Persisting goes through progress.write_step_hashes instead of
    setting the two columns here, for the same reason every other RunStep
    transition in progress.py commits immediately: a process can die
    between this call and the step's outcome, and
    engine.reconcile_manifest must still find these two values committed.

    A step that goes on to fail keeps what is written here, because the
    two values describe the attempt, not its outcome. A retry overwrites
    them with the identical result, since the inputs do not change between
    attempts. A step the engine skips for its condition never reaches this
    call, so its row keeps NULL for both: it never consumed anything.
    """
    write_step_hashes(
        context.session,
        row,
        input_sha256=input_sha256(step, context),
        reuse_key=reuse_key(step, context),
    )
