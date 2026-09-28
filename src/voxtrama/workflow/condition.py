"""A closed grammar for a step's `condition`, deliberately not a language.

A workflow file is something we invite people outside Voxtrama to write
(M2's criterion), and `eval` (even sandboxed, even restricted to a
whitelist of names) is code execution wearing a YAML disguise: the moment
a condition can call something, a third-party workflow can do more than
branch, and nobody reviewing that file would expect to have to check for
it. So this module recognises exactly one shape, `<path> <operator>
<literal>`, and refuses everything else rather than trying to make a
bigger grammar safe.

Only parsing lives here: what a path resolves to
depends on a run in progress, and belongs to engine.condition instead.
This is the same split as this file's own Workflow and engine.context.
"""

from __future__ import annotations

import json
import operator
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ConditionSyntaxError(ValueError):
    """A condition string does not match `<path> <operator> <literal>`."""


@dataclass(frozen=True)
class Condition:
    """A parsed condition: a path, an operator, and the literal to compare it to."""

    path: str
    operator: str
    literal: Any
    raw: str


# The only scalar paths a condition may read. Closed for the
# same reason as the grammar itself: a path is a promise about what a run
# exposes, and an open one would let a condition reach into whatever the
# engine happens to hold next.
SCALAR_PATHS = frozenset(
    {
        "recording.duration_seconds",
        "recording.media_type",
        "transcript.language",
        "transcript.speaker_estimate",
    }
)

# steps.<id>.<key>, reading what an earlier step produced.
STEPS_PATH = re.compile(r"^steps\.(?P<step_id>[^.]+)\.(?P<key>[^.]+)$")

# steps.<id>.state reads RunStep.state, not what the step produced. Only
# the three states a run settles on are comparable: `pending` and
# `running` describe a step still in flight, and a condition that read one of
# those would always be true or always false without saying anything real, so
# engine.condition raises instead of letting either reach here.
STEP_STATE_VALUES = frozenset({"succeeded", "failed", "skipped"})

# Ordering steps.<id>.state (`>`, `<`, ...) is meaningless: StepState is not
# ordered, and `>` would silently fall back to comparing the strings
# alphabetically. Only equality and membership say anything real about it.
STEP_STATE_OPERATORS = frozenset({"==", "!=", "in", "not in"})

OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
}
# Longest token first, so "not in" is recognised before "in" would match its
# own tail, and ">=" before ">" would swallow it.
_OPERATOR_TOKENS = sorted(OPERATORS, key=len, reverse=True)


def parse_condition(raw: str) -> Condition:
    """Parse `raw` as `<path> <operator> <literal>`, or raise ConditionSyntaxError.

    Parsed twice for the same condition in a real run: once by the loader
    at the workflow's load time, and once by the engine when the step is
    reached. Re-parsing there is the same choice engine.steps makes for
    depends_on: a workflow can reach the engine from somewhere that never
    ran the loader, and the engine must not trust that it did.
    """
    text = raw.strip()
    head = text.split(None, 1)
    if len(head) != 2:
        raise ConditionSyntaxError(f"malformed condition: '{raw}'")
    path, remainder = head
    check_path(path, raw)
    op_token, literal_text = _split_operator(remainder.strip(), raw)
    literal = _parse_literal(literal_text, raw)
    return Condition(path=path, operator=op_token, literal=literal, raw=raw)


def check_path(path: str, raw: str) -> None:
    """Raise ConditionSyntaxError unless `path` is one this grammar allows."""
    if path in SCALAR_PATHS or STEPS_PATH.match(path):
        return
    raise ConditionSyntaxError(
        f"condition names a path outside the allowed list: '{path}' in '{raw}'"
    )


def _split_operator(remainder: str, raw: str) -> tuple[str, str]:
    for token in _OPERATOR_TOKENS:
        if remainder == token or remainder.startswith(token + " "):
            return token, remainder[len(token) :].strip()
    raise ConditionSyntaxError(f"condition has no recognised operator: '{raw}'")


def _parse_literal(text: str, raw: str) -> Any:
    if not text:
        raise ConditionSyntaxError(f"condition has no literal after its operator: '{raw}'")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConditionSyntaxError(f"condition literal is not valid JSON: '{raw}'") from exc


def apply_operator(condition: Condition, actual: Any) -> bool:
    """Compare `actual` (whatever a run resolved condition.path to) against the literal."""
    return bool(OPERATORS[condition.operator](actual, condition.literal))
