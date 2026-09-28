"""ManifestFailure: the failure section of a manifest, for any run that ended badly.

Split from schema.py to keep that file under the project's size limit, the
same reason ManifestEvidence lives in evidence.py and ManifestChoices in
choices.py rather than there.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ManifestFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    step: str | None
