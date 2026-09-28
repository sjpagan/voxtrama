"""Builds the failure section of a manifest, and assembles the whole thing.

sections.py builds the run-level sections (run, input, environment,
languages, workflow). step_info.py builds one steps[] entry (split out
once that grew past the project's size limit). This file builds failure and
combines all three into the Manifest build_manifest returns. No I/O
here: see writer.py for how the result reaches disk.
"""

from __future__ import annotations

from typing import Any

from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep
from voxtrama.db.models.transcript import Transcript
from voxtrama.manifest.choices import choices_info
from voxtrama.manifest.environment import provider_info
from voxtrama.manifest.evidence import ClaimCount, evidence_info
from voxtrama.manifest.failure import ManifestFailure
from voxtrama.manifest.output import OUTPUT_FILENAME
from voxtrama.manifest.schema import Manifest, ManifestOutput
from voxtrama.manifest.sections import (
    environment_info,
    input_info,
    languages_info,
    run_info,
    workflow_info,
)
from voxtrama.manifest.step_info import is_generative, step_info
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.privacy import local_only_steps


def _failure_info(run: Run) -> ManifestFailure | None:
    """The failure section, for any run that ended badly, not only `failed`.

    The right test is "does this run have an error_code to show", not "is
    the state failed": `interrupted` carries one too, and so
    will `cancelled` once it is given one. A state check here would have
    to enumerate both by hand, the mistake db.models.run.is_final
    already fixed once, for the same two states, after run_info and
    cli.progress_view each kept their own hand-written list and both
    forgot `cancelled`.
    """
    if run.error_code is None:
        return None
    return ManifestFailure(code=run.error_code, message=run.error or "", step=run.error_step)


def build_manifest(
    run: Run,
    rows: list[RunStep],
    workflow: Workflow | None,
    skills: SkillRegistry,
    recording: Recording | None,
    transcript: Transcript | None,
    evidence: dict[str, ClaimCount] | None = None,
    produced: dict[str, dict[str, Any]] | None = None,
    *,
    output_digest: str | None = None,
) -> Manifest:
    """Assemble the manifest for `run` as it stands right now.

    Pure: every write point calls this with whatever it currently knows,
    and what changes between calls is the Run and its rows, never how a
    field is derived from them. `output_digest` is the sha256 write_run_output
    just returned for output.json. None only when that write
    itself failed, in which case outputs[] stays empty rather than claim a
    hash for a file that may not exist. `produced` is ExecutionContext's own
    dict, handed over as a plain `dict[str, dict[str, Any]]`, the
    same shape `evidence` already takes, for the same reason: manifest must
    not import engine (see manifest/evidence.py's docstring), so the caller
    that has the dict hands it over rather than this module reaching for it.
    """
    ordered_rows = sorted(rows, key=lambda row: row.position)
    outputs = [ManifestOutput(path=OUTPUT_FILENAME, sha256=output_digest)] if output_digest else []
    # Parsed once here, not inside each section: run.choices is the same
    # value whether environment_info reads the requested hardware_profile
    # from it or choices_info reports the whole thing.
    choices = RunChoices.model_validate(run.choices or {})
    called = any(row.started_at and is_generative(skills, row) for row in ordered_rows)
    return Manifest(
        run=run_info(run),
        input=input_info(recording),
        environment=environment_info(transcript, choices).model_copy(
            update={"provider": provider_info(get_settings(), choices.provider, called)}
        ),
        languages=languages_info(transcript),
        workflow=workflow_info(run, workflow).model_copy(
            update={"local_only_steps": local_only_steps(workflow, skills) if workflow else []}
        ),
        choices=choices_info(choices, run.deduced_context),
        steps=[step_info(row, skills, produced) for row in ordered_rows],
        outputs=outputs,
        evidence=evidence_info(evidence or {}),
        failure=_failure_info(run),
    )
