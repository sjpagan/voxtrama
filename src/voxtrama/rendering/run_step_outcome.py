"""Turns a RunStep's elapsed time into what the run page's chain shows under it.

Split out of rendering.run_page to keep that file under the project's file
limit. engine.step_progress.step_duration_seconds is the fact. This is
only the formatting choice attached to it, kept here instead of in a
template so the "0 rounds to nothing, not to a lie" rule lives in one
place. components/step_chain.html only reads the two plain values back.
"""

from __future__ import annotations

from voxtrama.db.models.step import RunStep
from voxtrama.engine.step_progress import step_duration_seconds


def duration_parts(step: RunStep) -> tuple[int | None, bool]:
    """(minutes, is_short) for `step`: minutes rounded to the nearest whole one.

    None/False when `step` never both started and finished (nothing to
    show). `is_short` means the real duration rounded to 0. A step that
    took measurable time shown as "0 min" would claim it took none, so
    the template shows "< 1 min" instead.
    """
    seconds = step_duration_seconds(step)
    if seconds is None:
        return None, False
    minutes = round(seconds / 60)
    return (None, True) if minutes == 0 else (minutes, False)
