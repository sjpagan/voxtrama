"""GET /runs/{id}/manifest.json: a job's manifest, ready to share.

The manifest leaves through the Recap tab's «Export» menu,
without the context's own text: the context names people and products,
and whoever receives only the result must not learn who took part. What
stays is that a context was given and whether Whisper got it cut
(choices.context_cut_for_transcription). The manifest.json on disk keeps
everything: this is a copy for sharing, never a rewrite of the record.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, status
from fastapi.responses import Response

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.routes.run_page_result import manifest_of
from voxtrama.config.paths import get_paths
from voxtrama.db.models.run import Run

router = APIRouter()

REMOVED = "[removed]"


def _remove_hosts(shared: dict) -> None:
    """A host maps the network behind it, so it leaves nowhere.

    Not only `steps[].host`: a provider's error names its host too ("... is
    unreachable", "... answered 500"), in the step's `error` and in the
    run's `failure.message`.
    """
    hosts = {step["host"] for step in shared["steps"] if step.get("host")}
    for step in shared["steps"]:
        if step.get("host"):
            step["host"] = REMOVED
        if step.get("error"):
            step["error"] = _without(step["error"], hosts)
    failure = shared.get("failure")
    if failure and failure.get("message"):
        failure["message"] = _without(failure["message"], hosts)


def _without(text: str, hosts: set[str]) -> str:
    for host in sorted(hosts, key=len, reverse=True):
        text = text.replace(host, REMOVED)
    return text


def shared_manifest(runs_dir: Path, run_id: str) -> dict | None:
    """The job's manifest without the context's text or any host, or None without one.

    Also what api.routes.job_package puts in the job's ZIP.
    """
    manifest = manifest_of(runs_dir, run_id)
    if manifest is None:
        return None
    shared = manifest.model_dump(mode="json")
    for field in ("context", "context_deduced"):  # a deduced one names people too
        if shared["choices"].get(field):
            shared["choices"][field] = REMOVED
    _remove_hosts(shared)
    return shared


def file_stem(run: Run) -> str:
    """The job's name as a file name: its label, else its workflow's."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", run.label or run.workflow_name).strip("-") or "job"


@router.get("/runs/{run_id}/manifest.json")
def manifest_export_route(run_id: str, session: DbDep, settings: SettingsDep) -> Response:
    """The job's manifest, with the context's text taken out, as a download."""
    run = get_run_or_404(run_id, session)
    shared = shared_manifest(get_paths(settings.data_dir).runs_dir, run.id)
    if shared is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="No manifest to export",
            detail=f"run '{run_id}' has no manifest yet",
        )
    return Response(
        json.dumps(shared, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{file_stem(run)}-manifest.json"'},
    )
