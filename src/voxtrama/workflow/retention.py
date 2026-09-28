"""How long a job's data stays: the three levels and the strictest wins.

The installation's own limit, the workflow's
(the `retention_policy` its skills declare) and the person's choice for
the job. The shortest wins: a workflow can shorten, never lengthen, and a
person can shorten, never lengthen past what the workflow declares. An
installation starts with no limit at all.

A skill's `retention_policy` is `follows_recording` (no limit of its own:
what it produces lives as long as the job) or a number of days, `30d`.
"""

from __future__ import annotations

from dataclasses import dataclass

FOLLOWS_RECORDING = "follows_recording"
POLICY_PATTERN = r"^(follows_recording|[1-9][0-9]{0,4}d)$"

INSTALLATION = "installation"
WORKFLOW = "workflow"
JOB = "job"


def policy_days(policy: str) -> int | None:
    """The days `policy` allows, None for `follows_recording`."""
    return None if policy == FOLLOWS_RECORDING else int(policy.removesuffix("d"))


def workflow_days(policies: list[str]) -> int | None:
    """The workflow's own limit: the shortest its skills declare."""
    days = [d for d in map(policy_days, policies) if d is not None]
    return min(days) if days else None


@dataclass(frozen=True)
class Retention:
    """The limit a job lives under, and which level set it."""

    days: int
    level: str


def strictest(installation: int | None, workflow: int | None, job: int | None) -> Retention | None:
    """The shortest of the three levels, None when none sets a limit."""
    levels = ((installation, INSTALLATION), (workflow, WORKFLOW), (job, JOB))
    chosen = [(days, name) for days, name in levels if days is not None]
    if not chosen:
        return None
    days, level = min(chosen, key=lambda pair: pair[0])
    return Retention(days=days, level=level)
