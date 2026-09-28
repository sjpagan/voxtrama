"""The window side of a generative step: what each call reads and says.

Split from engine.generative (the project's file size limit).
transcript_windows cuts, window_merge joins; this module fills one window's prompt, writes
the Activity panel's line for it, and records on the step how many
windows there were, which is what the manifest and the job's settings
line show (the split is visible).
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.db.models.step import RunStep
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.context_budget import FALLBACK_MAX_CTX
from voxtrama.engine.transcript_windows import Window, window_text
from voxtrama.setup.installation import read_installation_config
from voxtrama.workflow.output_languages import prompt_language
from voxtrama.workflow.skill import SAME_AS_AUDIO, Skill

logger = logging.getLogger(__name__)


def max_ctx_for(data_dir: Path, model: str) -> int:
    """`model`'s num_ctx ceiling, or FALLBACK_MAX_CTX when unmeasured."""
    config = read_installation_config(data_dir)
    if config is None:
        return FALLBACK_MAX_CTX
    return config.model_context_limits.get(model, FALLBACK_MAX_CTX)


def output_language(skill: Skill, transcript: Transcript, chosen: str | None = None) -> str:
    """The job's choice first. Else same_as_audio
    (a skill's default) resolves to the transcript's language."""
    if chosen:
        return prompt_language(chosen)
    if skill.output_language == SAME_AS_AUDIO:
        # The transcript stores a code ("it"), and a prompt that says
        # "written in it" reads as the English pronoun. The name goes in.
        return prompt_language(transcript.language)
    return prompt_language(skill.output_language)


def fill_prompt(template: str, transcript: str, language: str, detail: str = "") -> str:
    """The skill's prompt with the transcript lines (Segment.text only) filled in."""
    return template.format(language=language, transcript=transcript, detail=detail)


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600}:{whole // 60 % 60:02d}:{whole % 60:02d}"


def announce_window(segments: list[Segment], window: Window, number: int, count: int) -> None:
    """One Activity line per window of a split transcript: which part of the audio it reads."""
    if count == 1 or window.end <= window.start:
        return
    start, end = segments[window.start].start, segments[window.end - 1].end
    logger.info("Window %d of %d, %s to %s", number, count, _clock(start), _clock(end))


def window_prompts(
    segments: list[Segment], windows: list[Window], template: str, language: str, detail: str
) -> list[str]:
    """Each window's prompt, in order, with its Activity line written as it is built."""
    prompts = []
    for number, window in enumerate(windows, start=1):
        announce_window(segments, window, number, len(windows))
        text = window_text(segments, window, len(windows))
        prompts.append(fill_prompt(template, text, language, detail))
    return prompts


def record_windows(session: Session, row: RunStep, count: int) -> None:
    """How many windows the step's transcript was read in, committed at once."""
    row.transcript_windows = count
    session.commit()
