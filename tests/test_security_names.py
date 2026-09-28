"""Names that must never become paths or code."""

from __future__ import annotations

import pytest

from voxtrama.ingest.local_file import stored_name
from voxtrama.workflow.document import DocumentNotFoundError, find_document
from voxtrama.workflow.instructions import InstructionsError, check_instructions


@pytest.mark.parametrize("name", ["../../../../etc/x", "..", "a/b", "meeting.decisions", ""])
def test_a_workflow_name_is_never_a_path(name: str) -> None:
    with pytest.raises(DocumentNotFoundError):
        find_document("workflows", name, "workflow")


def test_a_real_workflow_name_is_still_found() -> None:
    assert find_document("workflows", "meeting-decisions", "workflow").name == (
        "meeting-decisions.yaml"
    )


@pytest.mark.parametrize(
    "text",
    [
        "{transcript:>999999999}",  # built a gigabyte string inside the check
        "{transcript} {transcript.__class__}",
        "{transcript} {language!r}",
        "{transcript} {other}",
    ],
)
def test_instructions_take_the_three_placeholders_bare(text: str) -> None:
    with pytest.raises(InstructionsError):
        check_instructions(text)


def test_good_instructions_pass() -> None:
    check_instructions("Summarize in {language}, {detail}: {{json}}\n{transcript}")


@pytest.mark.parametrize(
    ("uploaded", "kept_as"),
    [
        ("call.wav", "call.wav"),
        ("peaks-v3.json", "original-peaks-v3.json"),
        ("resampled_16k.wav", "original-resampled_16k.wav"),
        ("cleaned_16k_v1.wav", "original-cleaned_16k_v1.wav"),
    ],
)
def test_an_upload_never_takes_a_name_voxtrama_writes_beside_it(uploaded, kept_as) -> None:
    assert stored_name(uploaded) == kept_as
