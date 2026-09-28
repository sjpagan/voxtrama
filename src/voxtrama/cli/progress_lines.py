"""What one line of a run's progress says, in words.

Split from cli.progress_view, which owns *when* a line is printed and how
it is rewritten on a terminal. This owns only what it reads. Beyond the
file-length limit: the branch a line takes depends on which of three
things the engine published (an activity, a declared ceiling, neither),
and none of that has anything to do with carriage returns and polling.

Every string here is English: it is the source language, not
a default a catalogue replaces.
"""

from __future__ import annotations

from datetime import UTC, datetime

from voxtrama.engine.progress_state import Activity, ProgressState
from voxtrama.humanize import human_bytes, human_clock


def _position(state: ProgressState) -> str:
    """ "[2/3] " when the run knows where it is among its steps, else nothing."""
    if state.step_index is None or not state.step_total:
        return ""
    return f"[{state.step_index + 1}/{state.step_total}] "


def _describe_activity(activity: Activity) -> str:
    """One line for a step reporting its position from a loop of its own."""
    if activity.unit == "bytes":
        done = human_bytes(activity.done)
        if activity.total:
            percent = activity.done * 100 / activity.total
            total = human_bytes(activity.total)
            return f"downloading {activity.name}: {done} of {total} ({percent:.0f}%)"
        return f"downloading {activity.name}: {done}"
    done = human_clock(activity.done)
    if activity.total:
        return f"processing {activity.name}: {done} / {human_clock(activity.total)}"
    return f"processing {activity.name}: {done}"


def _elapsed_since(published_at: str) -> float | None:
    """Seconds since the engine published this state, or None if it cannot be read.

    None instead of an exception: a progress file whose timestamp is
    unparseable (hand-edited, or written by a version that spelled it
    differently) must not be the reason `voxtrama run` dies while
    following a run that is going fine.
    """
    try:
        return (datetime.now(UTC) - datetime.fromisoformat(published_at)).total_seconds()
    except (TypeError, ValueError):
        return None


def _describe_ceiling(state: ProgressState, interactive: bool) -> str:
    """One line for a step with no loop to measure, only its declared timeout.

    Keeps the step's name in front: four of the skills on disk are
    generative, so "asking the model" alone does not say which step is
    waiting.

    Elapsed is only shown interactively: it changes every second, and
    ProgressPrinter.render only re-prints a line that changed. In a log
    file that would be a line a second for the whole wait. Under the
    architecture's "engine publishes, it does not display", avoiding that
    noise is the renderer's job, not something the engine should throttle.
    """
    ceiling = state.ceiling_seconds
    elapsed = _elapsed_since(state.updated_at) if interactive else None
    if elapsed is None:
        return f"asking the model, up to {ceiling:.0f}s"
    return f"asking the model, {elapsed:.0f}s elapsed of {ceiling:.0f}s"


def describe_run_line(state: ProgressState, interactive: bool) -> str:
    """One line saying what the run is doing right now.

    The step position leads every line, not only the plain one. Without it
    "processing audio: 1:01 / 18:30" reads the same whether transcription
    just restarted or diarisation has begun. The two steps measure the
    same audio in the same unit, and only the position tells them apart.
    """
    position = _position(state)
    if state.activity is not None:
        return position + _describe_activity(state.activity)
    if state.ceiling_seconds is not None:
        return (
            position + f"{state.message or state.state}: " + _describe_ceiling(state, interactive)
        )
    return position + f"{state.message or state.state}"
