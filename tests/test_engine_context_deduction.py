"""A context deduced when none was declared."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

from voxtrama.db.models.transcript import Segment
from voxtrama.engine.context_deduction import (
    SAMPLES,
    deduce,
    prompt_context,
    sampled_excerpts,
)
from voxtrama.workflow.choices import RunChoices


@dataclass
class _Answer:
    text: str


class _Provider:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def generate(self, prompt: str, model: str, json_output: bool = False, **_: object):
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return _Answer(json.dumps(self.answer)), None


def _segments(count: int) -> list[Segment]:
    return [Segment(start=i * 10.0, end=i * 10.0 + 9, text=f"line {i}.") for i in range(count)]


_ANSWER = {
    "topic": "Planning the Q3 roadmap.",
    "people": ["Giulia", "Marco"],
    "products": ["TypeSense"],
    "acronyms": ["OKR"],
}


def test_the_excerpts_are_spread_over_the_whole_recording() -> None:
    text = sampled_excerpts(_segments(400))

    assert text.count("[...]") == SAMPLES - 1
    assert "line 0." in text and "line 399." in text


def test_the_answer_becomes_a_few_plain_lines() -> None:
    context = deduce(_Provider(_ANSWER), "m", _segments(20), "English")

    assert context == (
        "Topic: Planning the Q3 roadmap.\nPeople: Giulia, Marco\nProducts: TypeSense\nAcronyms: OKR"
    )


def _ctx(context: str | None = None, deduced: str | None = None):
    run = SimpleNamespace(deduced_context=deduced)
    session = SimpleNamespace(commit=lambda: None)
    transcript = SimpleNamespace(segments=_segments(30))
    return SimpleNamespace(
        choices=RunChoices(context=context), run=run, session=session, transcript=transcript
    )


def test_a_declared_context_is_used_and_nothing_is_deduced() -> None:
    provider = _Provider(_ANSWER)

    block = prompt_context(_ctx(context="Voxtrama, Whisper"), provider, "m", "English")

    assert "Context declared" in block and "Voxtrama, Whisper" in block
    assert provider.prompts == []


def test_without_one_it_is_deduced_once_marked_and_kept_on_the_run() -> None:
    provider = _Provider(_ANSWER)
    ctx = _ctx()

    first = prompt_context(ctx, provider, "m", "English")
    second = prompt_context(ctx, provider, "m", "English")

    assert len(provider.prompts) == 1
    assert first == second
    assert "deduced automatically" in first and "TypeSense" in first
    assert "the transcript wins" in first
    assert ctx.run.deduced_context.startswith("Topic:")


def test_a_deduction_that_fails_leaves_the_job_without_a_context() -> None:
    ctx = _ctx()

    block = prompt_context(ctx, _Provider(RuntimeError("model gone")), "m", "English")

    assert block == ""
    assert ctx.run.deduced_context == ""
