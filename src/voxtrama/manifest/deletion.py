"""The tombstone a job leaves once its content is deleted by retention.

The content goes (audio, transcript, recap,
outputs) and the manifest stays, emptied: only the fields that cannot
rebuild what was deleted (input hash, duration, steps run, models,
provider), plus `content_deleted`, which says when and under which limit.
It is the tombstone that proves the deletion happened.

A tombstone is still a Manifest: every reader of one reads the other.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ManifestDeletion(BaseModel):
    """When a job's content was deleted, and the limit that deleted it."""

    model_config = ConfigDict(extra="forbid")
    deleted_at: str
    retention_days: int
    # Which level set the limit: installation, workflow or job (workflow.retention).
    retention_level: str


def emptied(manifest: dict[str, Any], deletion: ManifestDeletion) -> dict[str, Any]:
    """`manifest` with every field that carries content taken out."""
    tomb = dict(manifest)
    tomb["run"] = {**manifest["run"], "label": None}
    if manifest.get("input"):
        tomb["input"] = {**manifest["input"], "source_url": None, "source_title": None}
    choices = {**manifest["choices"], "context": None}
    choices["context_deduced"] = None
    tomb["choices"] = choices
    tomb["steps"] = [{**step, "error": None} for step in manifest["steps"]]
    tomb["outputs"] = []
    if manifest.get("failure"):
        tomb["failure"] = {**manifest["failure"], "message": ""}
    tomb["content_deleted"] = deletion.model_dump()
    return tomb
