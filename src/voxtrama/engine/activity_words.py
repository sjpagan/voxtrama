"""What the live activity line says a step is doing.

It said "processing audio" for transcription and diarisation alike, and
"downloading <model>" for a download, which read as a machine talking to
itself. A step now says what it does; anything else keeps the generic verb
for its unit. Read with .get everywhere: a step or unit nobody named here
degrades the wording, it never raises inside a running step.
"""

from __future__ import annotations

_BY_STEP = {
    "transcribe": "transcribing the audio",
    "diarize": "telling the speakers apart",
    "summarize": "writing the recap",
    "extract_decisions": "finding the decisions",
    "extract_themes": "finding the themes",
    "extract_concepts": "finding the key concepts",
}
_VERB = {"bytes": "downloading", "seconds": "processing"}


def step_sentence(step_id: str, skill: str) -> str:
    """What a step is doing, by its id or else its skill; "running <skill>" otherwise."""
    return _BY_STEP.get(step_id) or _BY_STEP.get(skill) or f"running {skill}"


def activity_message(step_id: str, unit: str, name: str) -> str:
    """The lower-case sentence progress.json carries for this step's activity."""
    if unit == "bytes":  # a model download inside a step names the model
        return f"downloading {name}"
    if unit == "windows":  # a generative step counting the windows answered
        return _BY_STEP.get(step_id, "reading the transcript")
    return _BY_STEP.get(step_id, f"{_VERB.get(unit, 'processing')} {name}")
