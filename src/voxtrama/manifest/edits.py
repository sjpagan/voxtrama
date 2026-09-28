"""A person's corrections to a job's verified output, kept beside it.

A point of the recap or of an extraction can be rewritten, or tied to
another turn of the transcript. The correction is written to
`runs/<id>/edits.json`, never into output.json: that file is what the
model produced, the manifest hashes it (steps[].output_sha256), and it
must keep saying so. The job view and the exports read output.json with
the edits laid over it (apply_edits), and mark each changed point.

A point is named by where it sits: `<step id>/<array>/<index>`, e.g.
`summarize/key_points/3`. The output of a finished job never changes, so
the index is stable for as long as the job exists.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from voxtrama.manifest.output import RunOutput

EDITS_FILENAME = "edits.json"


def edits_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / run_id / EDITS_FILENAME


def read_edits(runs_dir: Path, run_id: str) -> dict[str, dict[str, Any]]:
    """The job's corrections by point, empty when there are none or the file is unreadable."""
    try:
        data = json.loads(edits_path(runs_dir, run_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_edit(runs_dir: Path, run_id: str, ref: str, edit: dict[str, Any]) -> None:
    """Record `edit` for the point `ref`, replacing an earlier one."""
    edits = read_edits(runs_dir, run_id)
    edits[ref] = edit
    path = edits_path(runs_dir, run_id)
    partial = path.with_name(EDITS_FILENAME + ".part")
    partial.write_text(json.dumps(edits, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.replace(path)


def point_at(output: RunOutput, ref: str) -> dict[str, Any] | None:
    """The claim `ref` names in `output`, or None when there is no such point."""
    step_id, _, rest = ref.partition("/")
    key, _, index = rest.partition("/")
    claims = (output.steps.get(step_id) or {}).get(key)
    if not isinstance(claims, list) or not index.isdigit() or int(index) >= len(claims):
        return None
    claim = claims[int(index)]
    return claim if isinstance(claim, dict) else None


def apply_edits(
    output: RunOutput, edits: dict[str, dict[str, Any]], text_fields: dict[str, str]
) -> RunOutput:
    """`output` with every edit laid over it. `text_fields` maps an array to its text field.

    An edited point says so (`edited`), and one tied to a turn by hand
    counts as verified: its evidence is that turn, and it no longer needs
    review.
    """
    if not edits:
        return output
    changed = copy.deepcopy(output)
    for ref, edit in edits.items():
        claim = point_at(changed, ref)
        if claim is None:
            continue
        field = text_fields.get(ref.split("/")[1])
        if field and isinstance(edit.get("text"), str):
            claim[field] = edit["text"]
        if isinstance(edit.get("start"), (int, float)) and isinstance(
            edit.get("end"), (int, float)
        ):
            claim["evidence"] = {"start": edit["start"], "end": edit["end"]}
            claim["needs_review"] = False
        claim["edited"] = True
    return changed
