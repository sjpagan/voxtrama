"""What GET /runs/{id}/view's failed-state banner shows.

Only a Run in `failed` or `interrupted` state gets one (api.routes.
run_page decides that, not this module). `cancelled` is a person's
choice, not a fact this banner exists to explain. Which title and buttons
a code gets is a closed dispatch, in the spirit of engine.validation.
error_code_for's docstring on its taxonomy. A code this module does not
recognise still gets a banner, one that shows `raw_error` as-is instead
of pretending to know more (never invented, and there is
nothing to compose from an exception message this module never parses).

`MemoryFacts` carries the chunking numbers: the parallel_chunks and
cores_per_chunk this run used, and what tuning.selector's file
recommends for this machine. The route reads them (Settings, read_machine,
select_tuning: none of that belongs in rendering). They are only *chosen*
to appear here, never computed. `notice` is tuning/*.yaml's
MemoryThreshold.warning, already formatted with this machine's real
reading (that sentence is never composed again here).
"""

from __future__ import annotations

from dataclasses import dataclass

# `interrupted` is folded in here instead of reading as "internal". The
# worker-vanished case (engine.reconcile) never raises into error_code_for,
# so nothing there could have named it "memory". But a worker that stops
# answering mid-step is one of the three symptoms of a memory failure
# (killed by the system, MemoryError, process gone), so the machine's
# configuration is worth naming for it too. It is hedged, not asserted
# (components/run_failure_banner.html's wording), since an orderly
# `docker compose down` looks identical to reconcile_orphan_runs and this
# module cannot tell them apart.
_MEMORY_CODES = frozenset({"memory_exhausted", "interrupted"})

# The generative model is the missing piece ("No summary model
# reachable"): configured nowhere, or configured and not
# answering. Either way the transcript is saved and Settings is the remedy.
_MODEL_CODES = frozenset({"generative_model_not_configured", "generative_model_unreachable"})


@dataclass(frozen=True)
class MemoryFacts:
    """The chunking configuration a memory-flavoured banner names."""

    used_parallel_chunks: int
    used_cores_per_chunk: int
    recommended_parallel_chunks: int
    recommended_cores_per_chunk: int
    notice: str | None


@dataclass(frozen=True)
class FailureAction:
    """One of the banner's buttons: which label components/run_failure_banner.html
    picks, and where it leads."""

    key: str
    href: str


@dataclass(frozen=True)
class FailureBanner:
    """The banner GET /runs/{id}/view shows for a failed or interrupted run.

    `title_key` is None only for a code this module does not recognise,
    the one case where `message` carries anything (`raw_error` verbatim).
    """

    code: str
    title_key: str | None
    message: str | None
    memory: MemoryFacts | None
    actions: tuple[FailureAction, ...]


def failure_banner_view(
    error_code: str,
    raw_error: str | None,
    memory: MemoryFacts,
    *,
    model_settings_href: str,
    processing_settings_href: str,
    retry_href: str,
) -> FailureBanner:
    """The banner for a Run whose error_code is `error_code`. Always one, never None.

    Called only once api.routes.run_page has decided this run gets a
    banner (state is `failed` or `interrupted`). Other states never reach
    this call. `memory` is passed for every code (cheap to read, one
    branch instead of two call shapes) and only kept on the codes that
    use it.
    """
    retry = FailureAction("retry", retry_href)
    if error_code in _MODEL_CODES:
        return FailureBanner(
            code=error_code,
            title_key=error_code,
            message=None,
            memory=None,
            actions=(FailureAction("open_settings", model_settings_href), retry),
        )
    if error_code in _MEMORY_CODES:
        return FailureBanner(
            code=error_code,
            title_key=error_code,
            message=None,
            memory=memory,
            actions=(FailureAction("open_settings", processing_settings_href), retry),
        )
    if error_code == "job_timeout":
        return FailureBanner(
            code=error_code, title_key=error_code, message=raw_error, memory=None, actions=(retry,)
        )
    return FailureBanner(
        code=error_code, title_key=None, message=raw_error, memory=None, actions=(retry,)
    )
