"""The declared context in a generative prompt.

Whisper only takes the first ASR_CONTEXT_CHARS of it. A generative model
has no such limit, so it gets all of it, ahead of the skill's prompt, with
the rule that decides a conflict written next to it: what was said in the
recording wins over what someone expected it to say. A deduced context
(engine.context_deduction) has its own wording: nobody
wrote it, and it says so.
"""

from __future__ import annotations

_BLOCK = (
    "Context declared by the person who submitted this recording (names, acronyms,\n"
    "topics). Use it to spell names and terms correctly. If it conflicts with the\n"
    "transcript, the transcript wins: never report something only the context says.\n"
    "---\n"
    "{context}\n"
    "---\n\n"
)

# A deduced context says so, and weighs less than a declared one.
_DEDUCED = (
    "Context deduced automatically from excerpts of this same transcript (topic, names,\n"
    "acronyms). It may be wrong: use it only to spell names and terms the transcript\n"
    "already contains. If it conflicts with the transcript, the transcript wins.\n"
    "---\n"
    "{context}\n"
    "---\n\n"
)


def context_block(context: str | None, deduced: bool = False) -> str:
    """The block to put before a generative prompt, or nothing without a context."""
    if not context or not context.strip():
        return ""
    return (_DEDUCED if deduced else _BLOCK).format(context=context.strip())
