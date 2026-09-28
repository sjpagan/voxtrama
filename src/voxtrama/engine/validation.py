"""Checks what a step produced against the output_schema its Skill declares.

A run whose output does not match what its skill
promised must fail loudly, not degrade into a result that looks complete
and is not. Centralised here instead of left to each built-in, so a new
skill gets the check for free without having to remember to call it (see
engine.run, which calls validate_output right after a step returns).
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from voxtrama.engine.anchoring import EvidenceNotAnchored
from voxtrama.engine.generation_resume import GenerationTruncatedError, PromptTruncatedError
from voxtrama.engine.generative import OllamaModelNotConfiguredError
from voxtrama.providers.base import PrivacyViolation, ProviderTimeoutError, ProviderTransportError
from voxtrama.queue.errors import JobTimeoutError
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.rejection import ChoicesRejected
from voxtrama.workflow.skill import Skill


class UnknownSkillError(RuntimeError):
    """A step names a skill, or skill version, the registry has no declaration for."""


class OutputSchemaViolation(RuntimeError):
    """A step's output does not match its skill's declared output_schema."""


def resolve_skill(skills: SkillRegistry, skill_name: str, skill_version: str) -> Skill:
    """Look up `skill_name`@`skill_version`, the same way validate_output does.

    execute_step needs the Skill itself, not just a pass/fail on its
    output: engine.anchoring reads model_class and evidence_required off
    it, and neither is available once validate_output has only returned
    the validated output.
    """
    versions = skills.get(skill_name, {})
    skill = versions.get(skill_version)
    if skill is None:
        raise UnknownSkillError(
            f"no declaration for skill '{skill_name}' version '{skill_version}'"
        )
    return skill


def validate_output(
    skills: SkillRegistry, skill_name: str, skill_version: str, output: dict[str, Any]
) -> dict[str, Any]:
    """Validate `output` against `skill_name`@`skill_version`'s output_schema.

    Returns `output` unchanged, so a caller can write it straight to
    ctx.produced without resolving the skill a second time.
    """
    skill = resolve_skill(skills, skill_name, skill_version)
    validator = Draft202012Validator(skill.output_schema)
    errors = sorted(validator.iter_errors(output), key=lambda error: list(error.path))
    if errors:
        detail = "; ".join(_describe(error) for error in errors)
        raise OutputSchemaViolation(f"{skill_name}@{skill_version} output: {detail}")
    return output


def _describe(error: JsonSchemaValidationError) -> str:
    location = ".".join(str(part) for part in error.path) or "<root>"
    return f"{location}: {error.message}"


# Run.error.code for each exception class, first match wins. Two of these
# are ones a failed job's banner can act on: a model server that never
# answered (Open settings), and a job stopped for running past the time it
# was granted (Retry). Both used to read "internal", which nobody can act on.
_ERROR_CODES: tuple[tuple[type[BaseException], str], ...] = (
    (OutputSchemaViolation, "output_schema_violation"),
    (EvidenceNotAnchored, "evidence_not_anchored"),
    (PrivacyViolation, "privacy_violation"),
    (ProviderTimeoutError, "provider_timeout"),
    (ProviderTransportError, "generative_model_unreachable"),
    # One code for both truncations. The step refused to
    # hand back a result it could not vouch for as complete.
    (PromptTruncatedError, "generation_truncated"),
    (GenerationTruncatedError, "generation_truncated"),
    (ChoicesRejected, "choices_rejected"),
    # The failure banner points at "Open settings" for this one.
    (OllamaModelNotConfiguredError, "generative_model_not_configured"),
    # Memory ran out inside this process. A worker that
    # vanished never raises here (engine.reconcile's "interrupted").
    (MemoryError, "memory_exhausted"),
    (JobTimeoutError, "job_timeout"),
)


def error_code_for(exc: Exception) -> str:
    """Run.error.code for `exc`: its own if it has one, else "internal".

    This taxonomy is closed too, but it is not the HTTP one: that one is for
    HTTP errors (`rule_rejected`, `not_found`, ...), and Run.error's
    structure is kept explicitly separate from it. This function picks
    from the second, unenumerated one. The two are easy to unify by
    mistake later.
    """
    for kind, code in _ERROR_CODES:
        if isinstance(exc, kind):
            return code
    return "internal"
