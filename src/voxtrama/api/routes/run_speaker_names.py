"""POST /recordings/{recording_id}/speaker-names: the "Name speakers"
panel's own Save ("give a name").

A plain form POST, the model api.routes.workflow_edit's own
`step_skill__<id>` fields already set for a form with a variable number of
rows: components/speaker_naming_panel.html renders one `speaker_name__
<label>` input per detected voice, and this route reads them back by that
same prefix rather than a fixed set of fields it would have to keep in
sync with however many speakers a given run has.

Redirects to the run page the panel was opened from (`run_id`, a hidden
field the form carries) rather than the Recording itself, the same
after-POST redirect every mutating route here ends on (api.routes.
run_retry, api.routes.theme). It is a plain string built from client-supplied
input, not a path this route re-validates: the worst a tampered value can
do is redirect to a run page that does not exist, no different in kind
from typing that URL by hand.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from starlette.datastructures import FormData

from voxtrama.api.deps import DbDep
from voxtrama.api.routes.recording_lookup import get_recording_or_404
from voxtrama.db.speaker_naming import SpeakerNameEntry, add_speaker, save_speaker_names

router = APIRouter()

_NAME_PREFIX = "speaker_name__"


def _split_name(raw: str) -> tuple[str, str]:
    """ "Sarah" -> ("Sarah", ""); "Jane Doe" -> ("Jane", "Doe").

    The panel carries one field per voice,
    db.people._display_name's own join undone: split on the first space,
    not the last, so a two-word family name ("Van Halen") stays whole in
    `family_name` rather than losing its first half to `given_name`.
    """
    given, _, family = raw.strip().partition(" ")
    return given, family


def _entries(form: FormData) -> list[SpeakerNameEntry]:
    """Every `speaker_name__<label>` field the panel submitted, blank ones
    dropped: a blank field means that voice is left unnamed, not renamed
    to nothing (db.speaker_naming.save_speaker_names's own docstring)."""
    entries = []
    for key, value in form.multi_items():
        if not key.startswith(_NAME_PREFIX):
            continue
        raw = str(value).strip()
        if not raw:
            continue
        given, family = _split_name(raw)
        entries.append(
            SpeakerNameEntry(
                label=key.removeprefix(_NAME_PREFIX), given_name=given, family_name=family
            )
        )
    return entries


@router.post("/recordings/{recording_id}/speaker-names")
async def save_speaker_names_route(
    recording_id: str, request: Request, session: DbDep
) -> RedirectResponse:
    """Apply every named voice in the submitted form to `recording_id`."""
    get_recording_or_404(recording_id, session)
    form = await request.form()
    save_speaker_names(session, recording_id, _entries(form))
    return _back(form.get("run_id"))


def _back(run_id: object) -> RedirectResponse:
    """To the Speakers tab the form came from."""
    destination = f"/runs/{run_id}/view?tab=speakers" if run_id else "/"
    return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/recordings/{recording_id}/speakers")
async def add_speaker_route(
    recording_id: str, request: Request, session: DbDep
) -> RedirectResponse:
    """A speaker the detection missed, to give turns to in Explore."""
    get_recording_or_404(recording_id, session)
    form = await request.form()
    name = " ".join(str(form.get("name") or "").split())[:80]
    if name:
        add_speaker(session, recording_id, name)
    return _back(form.get("run_id"))
