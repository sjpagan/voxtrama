"""The fields a log line may carry: an allow-list.

An allow-list, not a block-list: a block-list fails open on the first field
nobody thought to forbid, where an allow-list fails closed on it. The project
bans transcripts, names, tokens, absolute paths and prompts from the logs.
Listing what passes makes that ban hold for the fifty things we did not
think of too.

Adding a field here is the review: it is the one place the decision is
visible in a diff.
"""

from __future__ import annotations

# Always present on every line, filled by the formatter itself.
CORE_FIELDS = frozenset({"ts", "level", "logger", "msg"})

# Present when the logging context (logs.context) has them set.
CONTEXT_FIELDS = frozenset({"run_id", "step", "job_id"})

# Present only when the caller passes them explicitly, e.g.
# logger.info("step finished", extra={"duration_ms": 18422}).
EXTRA_FIELDS = frozenset(
    {
        "duration_ms",
        "count",
        "code",
        "host",
        "model",
        "revision",
        "profile",
        "attempt",
    }
)

ALLOWED_FIELDS = CORE_FIELDS | CONTEXT_FIELDS | EXTRA_FIELDS
