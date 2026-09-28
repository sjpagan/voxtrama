"""Read a domain document (a workflow, a generative skill file, or the
generative model table) from YAML.

Governs domain documents only: the three YAML formats that validate against
a Pydantic model, workflow, skill file, and generative model table. It
has no opinion on any other YAML in the repository: compose.yaml and
CI configuration have no model to check against, and pointing this at them
would silently accept whatever is there.

Three things every domain document needs, whichever kind it is:

- where to look for one, given the name of its folder (its two
  roots, most specific first);
- how to find one by name, across those roots;
- how to read one, naming the file on every way that can fail.

All three are generic over the folder name (and, for reading, the
Pydantic model), so a workflow, a skill file and the generative model
table share one implementation of each instead of each copying the last.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from voxtrama.config.settings import get_settings

ModelT = TypeVar("ModelT", bound=BaseModel)

# Every folder a domain document can live in, and the single list anything that
# has to ship them reads. Kept here rather than at each call site because the
# callers are not the only readers: the package and the image have to carry
# these folders, and this is what happened when one of them did not: skills/
# was never copied into the image, so the image had no generative skills and
# said "unknown skill" to every workflow naming one. A folder added here must be
# added to the Dockerfile too. tests/test_packaging_documents.py enforces that.
DOMAIN_DOCUMENT_FOLDERS = ("workflows", "skills", "model-catalog", "tuning")


def document_roots(folder: str) -> list[Path]:
    """Where to look for a document living in `folder`, most specific first.

    A domain document lives in two roots: the ones we ship are
    files of the package, read-only, and the ones a user writes or
    duplicates live in the data directory. The user's root wins when both
    hold the same name, so someone can try a modified copy without our
    file getting in the way, and neither file is ever written by the
    other.
    """
    roots = [get_settings().data_dir / folder]
    # The package's own documents: /app/<folder> in the image, the
    # repository root in a checkout. Resolved from the working directory
    # rather than from this file, because `pip install .` puts the module
    # in site-packages while the document files stay next to the
    # application.
    roots.append(Path.cwd() / folder)
    source_root = Path(__file__).resolve().parents[3] / folder
    if source_root not in roots:
        roots.append(source_root)
    return roots


class DocumentNotFoundError(FileNotFoundError):
    """No document named `name` under `folder`, in any of its roots.

    A FileNotFoundError, not just an Exception: a caller re-raises this as
    its own error type (WorkflowNotFoundError, SkillFileNotFoundError),
    both of which are already FileNotFoundError themselves, and something
    catching that ancestor must keep working.
    """


# A document is named like a slug: letters, digits, "-" and "_". Never a path.
DOCUMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


def find_document(folder: str, name: str, kind: str) -> Path:
    """The file called `name` under `folder`, across document_roots(folder).

    `kind` names what is being looked for in the error message ("workflow",
    "skill file"), so a caller's DocumentNotFoundError reads like its own.
    """
    searched = document_roots(folder)
    if not DOCUMENT_NAME.fullmatch(name):  # security: `../..` left the folder
        raise DocumentNotFoundError(f"no {kind} called {name!r}: not a valid name")
    for root in searched:
        candidate = root / f"{name}.yaml"
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            # A root we cannot even look inside is a root without the
            # document, not a failure: the data directory may default to a
            # path this process has no business reading, and letting that
            # stop the search would hide the document sitting in the next
            # one.
            continue
    looked_in = ", ".join(str(root) for root in searched)
    raise DocumentNotFoundError(f"no {kind} named '{name}' in: {looked_in}")


class DocumentError(Exception):
    """A domain document failed to load: bad file, malformed YAML, or a field pydantic rejected.

    Always names the file. A caller re-raises this as its own error type
    (WorkflowValidationError, SkillFileError) so whoever already catches
    that type sees no difference. See load_workflow and load_skill_file.
    """


def read_document(path: Path, model: type[ModelT]) -> ModelT:
    """Parse and validate `path` as `model`, naming `path` on every failure.

    Covers the three ways this can go wrong: the file cannot be read, the
    YAML does not parse, or it parses but does not match `model`. Unlike a
    malformed field, a parse error carries no loc pydantic could format:
    yaml's own message already says line and column, this only adds the
    one thing it cannot know: which file.
    """
    try:
        raw = yaml.safe_load(path.read_text())
    except OSError as exc:
        raise DocumentError(f"{path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise DocumentError(f"{path}: {exc}") from exc
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise DocumentError(_format_errors(path, exc)) from exc


def _format_errors(path: Path, exc: ValidationError) -> str:
    lines = (
        f"{path}: {'.'.join(str(p) for p in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    )
    return "\n".join(lines)
