"""Diarisation on the one audio file the repository carries.

This is the first test that can check speaker attribution in CI: until the
public fixture existed, every audio test lived outside the repository
and skipped. It downloads the ECAPA model on first run (the cost the whole
fixture was measured against) and caches it under the data directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.diarization import assign_speakers, speaker_count

FIXTURE = Path(__file__).parent / "fixtures" / "public-fixture.wav"
REFERENCE = Path(__file__).parent / "fixtures" / "public-fixture.rttm"


@pytest.fixture(scope="module")
def models_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One cache for the whole module: the model downloads once, not per test."""
    return tmp_path_factory.mktemp("diarization-models")


@pytest.fixture(scope="module")
def diarised(models_dir: Path) -> Transcript:
    """Diarise the fixture once and let every assertion read the same result."""
    return assign_speakers(_transcript_mirroring_the_reference(), FIXTURE, models_dir)


def _reference_turns() -> list[tuple[float, float, str]]:
    turns = []
    for line in REFERENCE.read_text().strip().splitlines():
        fields = line.split()
        start, duration, speaker = float(fields[3]), float(fields[4]), fields[7]
        turns.append((start, start + duration, speaker))
    return turns


def _transcript_mirroring_the_reference() -> Transcript:
    """A Transcript whose Segments match the reference turns.

    The ASR is not involved here on purpose: this test asks whether
    diarisation attributes known stretches of audio to the right voices, and
    running speech recognition first would let a transcription error look
    like an attribution error.
    """
    transcript = Transcript(
        recording_id="r1",
        language="en",
        model_name="medium",
        model_revision="test",
        hardware_profile="base",
    )
    transcript.segments = [
        Segment(start=start, end=end, text="", confidence=1.0)
        for start, end, _ in _reference_turns()
    ]
    return transcript


@pytest.mark.slow
def test_two_voices_are_told_apart(diarised: Transcript) -> None:
    assert speaker_count(diarised.segments) == 2


@pytest.mark.slow
def test_the_same_voice_gets_the_same_label_across_turns(diarised: Transcript) -> None:
    """Turns 1 and 3 are one voice, turns 2 and 4 the other.

    Counting two speakers is not enough on its own: a diarisation that
    alternated labels at every turn would also count two, and would be
    useless.
    """
    labels = [segment.speaker_label for segment in diarised.segments]
    assert labels[0] == labels[2]
    assert labels[1] == labels[3]
    assert labels[0] != labels[1]


@pytest.mark.slow
def test_person_id_is_never_written(diarised: Transcript) -> None:
    """Diarisation tells voices apart, it does not say who they are."""
    assert all(segment.person_id is None for segment in diarised.segments)
