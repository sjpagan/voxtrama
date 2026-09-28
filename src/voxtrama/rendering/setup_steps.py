"""The three-step tracker every guided-setup page shows.

The same three names the home page's status cards use ("Local
processing", "Model ready", "Private storage"), so the wizard and the
home page describe the same steps in the same words. "Personal settings"
opened the wizard until the name moved out of it.

Completion is purely positional: every step before `current` reads as
done, `current` is current, everything after is upcoming. The wizard is
linear and skippable (zero mandatory decisions), so there is
no separate "visited but unfinished" state to track. Landing on a step
means every step before it was either completed or skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SetupStepKey = Literal["processing", "models", "storage"]
SetupStepState = Literal["done", "current", "upcoming"]

# "Personal settings" left the wizard. The name is asked
# when it is needed, from the profile page, never before a first result.
_KEYS: tuple[SetupStepKey, ...] = ("processing", "models", "storage")


@dataclass(frozen=True)
class SetupStepRow:
    """One entry in the tracker: which step, and where it stands."""

    key: SetupStepKey
    state: SetupStepState


def setup_step_rows(current: SetupStepKey) -> list[SetupStepRow]:
    """The three steps in their fixed order, `current` marked and the rest positional."""
    index = _KEYS.index(current)
    return [
        SetupStepRow(
            key=key, state="done" if i < index else "current" if i == index else "upcoming"
        )
        for i, key in enumerate(_KEYS)
    ]
