"""The context of a recording nobody described, deduced from its transcript.

When a job declares no context, the engine deduces one
before the first model step, with one call on excerpts sampled across the
whole recording, not only its beginning, which is greetings and small
talk. It asks for the topic, the people named, the products and the
acronyms, and turns the answer into a few plain lines.

The deduced context is marked as such in every prompt, with the same rule
as a declared one: in a conflict the transcript wins. It is kept on the
run (Run.deduced_context), so the manifest says what was used and where it
came from, and a job whose model steps are all reused deduces nothing.
A deduction that fails is logged and the job goes on without a context:
it was never asked for, so it must never be the reason a job fails.
"""

from __future__ import annotations

import json
import logging

from voxtrama.db.models.transcript import Segment
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.context_prompt import context_block
from voxtrama.providers.base import TextProvider

logger = logging.getLogger(__name__)

SAMPLES = 8
SAMPLE_CHARS = 600
_FIELDS = (
    ("topic", "Topic"),
    ("people", "People"),
    ("products", "Products"),
    ("acronyms", "Acronyms"),
)

_PROMPT = """Below are excerpts sampled across the whole transcript of one recording.
Say what the recording is about and which names it uses, so that a later
reader spells them right. Only names that appear in the excerpts; nothing
you would have to guess. Answer in {language}, as JSON:
{{"topic": "one sentence", "people": [], "products": [], "acronyms": []}}

Excerpts:
{excerpts}
"""


def sampled_excerpts(segments: list[Segment]) -> str:
    """SAMPLES stretches of about SAMPLE_CHARS each, spread evenly over the transcript."""
    if not segments:
        return ""
    count = min(SAMPLES, len(segments))
    starts = sorted({round(i * (len(segments) - 1) / max(1, count - 1)) for i in range(count)})
    pieces = []
    for start in starts:
        taken, size = [], 0
        for segment in segments[start:]:
            if size >= SAMPLE_CHARS:
                break
            taken.append(segment.text.strip())
            size += len(segment.text)
        pieces.append(" ".join(taken))
    return "\n[...]\n".join(pieces)


def _as_lines(answer: dict) -> str:
    lines = []
    for key, label in _FIELDS:
        value = answer.get(key)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if str(item).strip())
        if isinstance(value, str) and value.strip():
            lines.append(f"{label}: {value.strip()}")
    return "\n".join(lines)


def deduce(provider: TextProvider, model: str, segments: list[Segment], language: str) -> str:
    """The deduced context as plain lines; empty when the model gave nothing usable."""
    prompt = _PROMPT.format(language=language, excerpts=sampled_excerpts(segments))
    result, _ = provider.generate(prompt, model, json_output=True)
    answer = json.loads(result.text)
    return _as_lines(answer) if isinstance(answer, dict) else ""


def prompt_context(ctx: ExecutionContext, provider: TextProvider, model: str, language: str) -> str:
    """The context block for this run's prompts: declared, else deduced once, else nothing."""
    if ctx.choices.context and ctx.choices.context.strip():
        return context_block(ctx.choices.context)
    if ctx.run.deduced_context is None and ctx.transcript is not None:
        logger.info("Deducing the context from the transcript")
        try:
            ctx.run.deduced_context = deduce(provider, model, ctx.transcript.segments, language)
        except Exception:
            logger.exception("could not deduce a context; going on without one")
            ctx.run.deduced_context = ""
        ctx.session.commit()
    return context_block(ctx.run.deduced_context, deduced=True)
