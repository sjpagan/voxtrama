"""The run page's activity log in a reader's words.

Split out of logs.tail (the project's file-length limit). That module reads
run.log and decides which lines reach the panel. This one only rewords
the engine's few fixed sentences on the way.
"""

from __future__ import annotations

# The engine's own narrative (engine.run, engine.preparation, engine.failure)
# says what happened in a developer's words. The panel says it in a
# reader's. Only the panel rewords it: run.log keeps the original.
_RUN_WORDS = {"run started": "Job started", "run finished": "Job done", "run failed": "Job failed"}
_STEP_STARTED = {"transcribe": "Transcribing the audio...", "diarize": "Identifying speakers..."}


def readable(msg: str, step: object) -> str:
    """`msg` as the panel says it. A step's start and end name the step."""
    if msg in _RUN_WORDS:
        return _RUN_WORDS[msg]
    if not isinstance(step, str) or msg not in ("step started", "step finished"):
        return msg
    title = step.replace("_", " ").capitalize()
    if msg == "step finished":
        return f"{title} done"
    return _STEP_STARTED.get(step, f"{title}...")
