"""Who spoke when: the chosen diarisation backend, wired into the product.

The package's public surface is `assign_speakers`, which takes a Transcript
the ASR has already produced and fills in the anonymous speaker label of each
Segment. It never writes `person_id` itself: that is a human's decision.
`reapply_known_speakers` is the one place this package
writes `person_id` at all, and it does not decide anything either: it
restores a decision a human already made on an earlier run of the same
Recording, read back from db.models.speaker_name.SpeakerName.
"""

from voxtrama.diarization.assign import assign_speakers, speaker_count
from voxtrama.diarization.speaker_names import reapply_known_speakers

__all__ = ["assign_speakers", "reapply_known_speakers", "speaker_count"]
