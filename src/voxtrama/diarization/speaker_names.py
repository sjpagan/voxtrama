"""Reapply a name a human already gave a speaker, across reprocessing.

Linking a label to a Person is "a separate, reversible act
performed by a human". This module does not perform that act. It restores
one already made. db.speaker_naming.save_speaker_names writes a
SpeakerName row once, keyed by (recording_id, speaker_label). Every later
diarisation of the same Recording reads it back here, onto the fresh
Segment rows that run's transcription just produced, so a name given once
survives a rerun without asking again: "Names apply to this recording and
stay attached if it is re-processed".

A label that recurs across runs is an assumption, not a certainty: this
relies on the diarisation backend assigning `spk0`/`spk1` in the same
order for the same audio, the only signal available without the voice
fingerprints already ruled out. A rerun with a different backend, or
one that finds a different number of speakers, may reapply a name to the
wrong voice. A label alone cannot tell, and this module does not try to.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.speaker_name import SpeakerName
from voxtrama.db.models.transcript import Transcript


def reapply_known_speakers(session: Session, recording_id: str, transcript: Transcript) -> None:
    """Set `person_id` on every Segment of `transcript` whose label was named before.

    A no-op for a Recording where nobody has named a speaker (the common
    case), checked once via `mapping` rather than a query per Segment.
    """
    mapping = {
        row.speaker_label: row.person_id
        for row in session.scalars(
            select(SpeakerName).where(SpeakerName.recording_id == recording_id)
        )
    }
    if not mapping:
        return
    for segment in transcript.segments:
        if segment.speaker_label in mapping:
            segment.person_id = mapping[segment.speaker_label]
