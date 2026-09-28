"""The declared context in the generative prompt and in the manifest."""

from __future__ import annotations

from voxtrama.engine.context_prompt import context_block
from voxtrama.manifest.choices import choices_info
from voxtrama.workflow.choices import (
    ASR_CONTEXT_CHARS,
    RunChoices,
    context_for_transcription,
)


def test_the_whole_context_reaches_the_prompt_with_the_rule_on_conflicts() -> None:
    long_context = "TypeSense, OKR, Giulia Rossi. " * 40
    block = context_block(long_context)

    assert long_context.strip() in block
    assert "the transcript wins" in block


def test_no_context_adds_nothing_to_the_prompt() -> None:
    assert context_block(None) == "" and context_block("   ") == ""


def test_transcription_gets_the_first_characters_and_the_manifest_says_so() -> None:
    long_context = "x" * (ASR_CONTEXT_CHARS + 50)

    assert context_for_transcription(long_context) == "x" * ASR_CONTEXT_CHARS
    assert choices_info(RunChoices(context=long_context)).context_cut_for_transcription is True
    assert choices_info(RunChoices(context="TypeSense")).context_cut_for_transcription is False
    assert choices_info(RunChoices()).context_cut_for_transcription is None
