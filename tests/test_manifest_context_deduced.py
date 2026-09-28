"""The manifest says which context was used and where it came from."""

from __future__ import annotations

from voxtrama.manifest.choices import choices_info
from voxtrama.workflow.choices import RunChoices


def test_a_deduced_context_is_in_the_manifest() -> None:
    info = choices_info(RunChoices(), "Topic: roadmap")

    assert info.context is None
    assert info.context_deduced == "Topic: roadmap"


def test_a_declared_context_has_nothing_deduced_beside_it() -> None:
    info = choices_info(RunChoices(context="Voxtrama"), None)

    assert info.context == "Voxtrama"
    assert info.context_deduced is None
