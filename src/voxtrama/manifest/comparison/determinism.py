"""The determinism gate: when two runs' outputs may legitimately vary.

Two granularities, because they judge two different things:

- `steps[<id>].output_sha256` is judged per step, against that step's own
  `deterministic`:
  `steps[].output_sha256` is the hash of only what that one step produced,
  serialized with `jsonfile.serialize` and carrying no run id (step_info.py).
  `output_hash_reason` below judges it. `outputs[*].sha256`, by contrast,
  hashes output.json (the envelope of every step's output under a run
  id), so it always differs and never reaches this gate. It is
  unconditionally expected instead (comparison/difference.py explains
  why).
- `evidence.claims` and `evidence.needs_review` stay judged in aggregate,
  by `non_reproducible_reason` below, because they are sums over every
  step's evidence and no per-step version of either exists to check
  instead. Any non_deterministic or hardware-varying same_host step
  anywhere in the run is still license enough to let those two totals vary.

Every generative skill is `non_deterministic` (workflow.skill's own
`Skill.deterministic`, ModelClass.GENERATIVE branch). A workflow built
entirely of extractive skills keeps both gates closed unless the two runs
also differ in hardware on a same_host step. This module exists to keep
that comparison honest.
"""

from __future__ import annotations

from voxtrama.workflow.skill import Determinism

_HARDWARE_FIELDS = ("hardware_profile_used", "device")


def non_reproducible_reason(a: dict, b: dict) -> str | None:
    """Why `evidence.claims`/`evidence.needs_review` may differ between `a` and `b`, or None.

    `deterministic == None` (the skill could not be resolved, so the run
    failed before running it) is deliberately not checked: it grants no
    license to vary and is absent from both rules below.
    """
    return _non_deterministic_step(a) or _non_deterministic_step(b) or _same_host_mismatch(a, b)


def output_hash_reason(step_id: str, a: dict, b: dict) -> str | None:
    """Why `steps[step_id].output_sha256` may differ between `a` and `b`, or None if it must match.

    Only called once walk.py has already found the two steps to disagree,
    so `step_id` is assumed present on both sides. That is the assumption
    `_step_by_id` makes explicit by raising rather than guessing.
    """
    step_a, step_b = _step_by_id(a, step_id), _step_by_id(b, step_id)
    reason = _step_non_deterministic(step_a) or _step_non_deterministic(step_b)
    if reason is not None:
        return reason
    return _step_same_host_mismatch(step_a, step_b, a["environment"], b["environment"])


def _step_by_id(manifest: dict, step_id: str) -> dict:
    for step in manifest["steps"]:
        if step["step_id"] == step_id:
            return step
    raise KeyError(step_id)


def _step_non_deterministic(step: dict) -> str | None:
    if step["deterministic"] == Determinism.NON_DETERMINISTIC:
        return f"step '{step['step_id']}' is non_deterministic"
    return None


def _step_same_host_mismatch(step_a: dict, step_b: dict, env_a: dict, env_b: dict) -> str | None:
    """A same_host step opens the gate only when the two runs' hardware differs.

    On identical environments a same_host step must reproduce (that is
    what the value means), so the difference counts there instead.
    """
    if not _different_hardware(env_a, env_b):
        return None
    if (
        step_a["deterministic"] == Determinism.SAME_HOST
        or step_b["deterministic"] == Determinism.SAME_HOST
    ):
        step_id = step_a["step_id"]
        return f"step '{step_id}' is same_host and the two runs used different hardware"
    return None


def _non_deterministic_step(manifest: dict) -> str | None:
    for step in manifest["steps"]:
        if step["deterministic"] == Determinism.NON_DETERMINISTIC:
            return f"step '{step['step_id']}' is non_deterministic"
    return None


def _same_host_mismatch(a: dict, b: dict) -> str | None:
    """A same_host step opens the gate only when the two runs' hardware differs.

    On identical environments a same_host step must reproduce (that is
    what the value means), so the difference counts there instead.
    """
    if not _different_hardware(a["environment"], b["environment"]):
        return None
    for step in a["steps"] + b["steps"]:
        if step["deterministic"] == Determinism.SAME_HOST:
            return f"step '{step['step_id']}' is same_host and the two runs used different hardware"
    return None


def _different_hardware(env_a: dict, env_b: dict) -> bool:
    return any(env_a[field] != env_b[field] for field in _HARDWARE_FIELDS)
