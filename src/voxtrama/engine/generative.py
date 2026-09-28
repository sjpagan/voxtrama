"""Runs a generative skill loaded from a file: run_summarize, generalized.

One function for every generative skill. engine.builtin binds it to a
SkillFile with functools.partial, and that partial is already a
StepFunction, so a new generative skill costs a file and one line of
wiring, never a new function here.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from voxtrama.config.settings import get_settings
from voxtrama.engine.context import ExecutionContext, StepPreconditionError
from voxtrama.engine.context_budget import ContextBudget, compute_context_budget
from voxtrama.engine.context_deduction import prompt_context
from voxtrama.engine.generation_resume import ResumedGeneration
from voxtrama.engine.generative_progress import record_context_budget
from voxtrama.engine.generative_windows import (
    max_ctx_for,
    output_language,
    record_windows,
    window_prompts,
)
from voxtrama.engine.progress import record_provenance
from voxtrama.engine.summary_detail import detail_instruction, recording_minutes
from voxtrama.engine.transcript_windows import split_windows
from voxtrama.engine.window_cache import forget_window, window_key
from voxtrama.engine.window_calls import generate_windows
from voxtrama.engine.window_merge import merge_outputs
from voxtrama.engine.window_outputs import window_outputs
from voxtrama.providers import text_provider_for
from voxtrama.workflow.skill_file import SkillFile


class OllamaModelNotConfiguredError(RuntimeError):
    """A generative step needs a model, and neither the run nor the machine named one.

    Which model to recommend is not decided yet. A default baked in
    here would quietly become that recommendation.
    """


def run_generative(skill_file: SkillFile, ctx: ExecutionContext) -> dict[str, Any]:
    """Ask the configured Ollama model for skill_file's prompt, filled in with ctx.transcript.

    Provider errors and PrivacyViolation are not caught here:
    engine.validation.error_code_for turns them into the run's failure,
    and engine.validation.validate_output checks the return value's schema.
    """
    skill = skill_file.skill
    if ctx.transcript is None:
        raise StepPreconditionError(
            f"{skill.name}: no Transcript to work from, transcribe it first"
        )
    settings = get_settings()
    # The run's choice wins over the machine's setting.
    model = ctx.choices.generative_model or settings.ollama_model
    if model is None:
        raise OllamaModelNotConfiguredError(
            "no generative model: the run chose none and VOXTRAMA_OLLAMA_MODEL is not set"
        )
    # Checked before the provider is asked anything. None means this ran
    # outside the engine, and a transcript must never go to a model (maybe
    # remote) with nowhere to record where it ran.
    step_id = ctx.current_step_id
    if step_id is None:
        raise StepPreconditionError(f"{skill.name}: no running step to file the provenance under")

    level = ctx.choices.summary_detail or settings.summary_detail
    return _read_in_windows(ctx, skill_file, model, step_id, level)


def _read_in_windows(
    ctx: ExecutionContext, skill_file: SkillFile, model: str, step_id: str, level: int
) -> dict[str, Any]:
    """Read window by window, outputs joined; windows sent together."""
    assert ctx.transcript is not None  # run_generative checked it
    segments = ctx.transcript.segments
    windows = split_windows(segments)
    language = output_language(skill_file.skill, ctx.transcript, ctx.choices.output_language)
    provider = text_provider_for(
        skill_file.skill, ctx.choices.provider, ctx.kept_local.get(step_id)
    )
    block = prompt_context(ctx, provider, model, language)
    template = ctx.instructions.get(step_id, skill_file.prompt)  # a custom step's own
    detail = detail_instruction(level, len(windows), recording_minutes(segments))
    prompts = [block + p for p in window_prompts(segments, windows, template, language, detail)]
    max_ctx = max_ctx_for(get_settings().data_dir, model)
    budgets = [compute_context_budget(prompt, max_ctx) for prompt in prompts]
    row = ctx.step_rows[step_id]
    generations = generate_windows(
        provider,
        prompts,
        model,
        budgets,
        get_settings().parallel_windows,
        cache_dir=get_settings().data_dir,  # A retry sends only unanswered windows
        on_answered=partial(_answered, ctx),
        on_failure=lambda index: record_context_budget(
            ctx.session,
            row,
            context_window_tokens=budgets[index].num_ctx,
            context_window_at_risk=budgets[index].at_risk,
            output_resumptions=None,
        ),
    )
    for budget, generation in zip(budgets, generations, strict=True):
        _record(ctx, step_id, budget, generation)
    record_windows(ctx.session, row, len(windows))
    outputs = window_outputs(  # A malformed point is dropped, not fatal
        generations,
        skill_file.skill.output_schema,
        lambda i: forget_window(get_settings().data_dir, window_key(model, prompts[i], budgets[i])),
    )
    return outputs[0] if len(outputs) == 1 else merge_outputs(outputs)


def _answered(ctx: ExecutionContext, done: int, total: int) -> None:
    if ctx.report_activity:
        ctx.report_activity("windows", "windows", done, total)


def _record(
    ctx: ExecutionContext, step_id: str, budget: ContextBudget, generation: ResumedGeneration
) -> None:
    """What one window's call used and where it ran, on the step's row.

    On the step's own thread: the Session is not shared with the calls' threads.
    """
    row = ctx.step_rows[step_id]
    record_context_budget(
        ctx.session,
        row,
        context_window_tokens=budget.num_ctx,
        context_window_at_risk=budget.at_risk,
        output_resumptions=generation.resumptions,
    )
    ctx.models[step_id] = generation.provenance
    record_provenance(
        ctx.session,
        row,
        model=generation.provenance.model,
        model_revision=generation.provenance.fingerprint,
        provider=generation.provenance.provider,
        host=generation.provenance.host,
        profile_check_skipped=generation.provenance.profile_check_skipped,
    )
