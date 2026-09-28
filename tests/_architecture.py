"""Shared layer data for the architecture checks.

test_architecture.py and test_architecture_imports.py both need to know
which layer a module belongs to (the first checks that every module is
classified, the second that core never imports outward), so the
classification lives here once instead of as two copies that could drift.
Not a test module itself: pytest only collects test_*.py, so nothing here
runs on its own.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "voxtrama"

# Every new module must be listed here: an unclassified module fails
# test_every_module_is_classified instead of passing silently. "queue" and
# "db" classify the package __init__ files, which re-export their package's
# public surface and hold no logic of their own (see the docstrings of
# queue/__init__.py and db/__init__.py. The latter explicitly re-exports the
# adapter, and db/migrations_state.py says of itself that it is an adapter,
# not core).
CORE = {
    "engine",
    "manifest",
    "queue",
    "queue.base",
    "queue.job",
    "queue.errors",
    "db.models",
    "workflow",
    "ingest",
    "transcription",
    "diarization",
    "weights",
    "providers",
    # Measures the machine and advises, never applies. Core
    # because it computes facts: the reading is taken here, and the CLI
    # writes the sentence a person reads.
    "diagnostics",
    "calibration",  # Inspects eval_dir. Reports facts, never a measure.
    # Where the demo's audio lives. A path, not a presentation.
    "demo",
    # Picks a tuning file by machine; hands back proposed parameters, never
    # applies them (same standing as diagnostics above).
    "tuning",
    # The guided first-run setup: reads the machine and proposes
    # numbers, same standing as diagnostics and tuning above. Its one
    # write (the installation config file) is a leaf artifact, not a
    # call into an adapter or an entrypoint.
    "setup",
    # The edition's signed limits: reads a block shipped with the
    # package and answers what is allowed. It depends on nothing but logs.
    "edition",
    "edition.policy",
    # Removing what nobody needs any more: a replaced job, the
    # clean-up. Reads and deletes rows and folders, calls nothing outward.
    # The engine uses it once a regenerated job succeeds.
    "housekeeping",
}
# "i18n.dependency" is a FastAPI dependency provider: it reads a Request
# and Settings, same shape as the entrypoints in api/, not a rule the
# domain needs. So it moves out of the i18n layer below and joins
# entrypoints (core does not import entrypoints).
ADAPTERS = {"queue.rq_backend", "db", "db.session"}
ENTRYPOINTS = {"api", "cli", "worker", "i18n.dependency"}
CONFIG = {"config"}  # read by everyone, depends on nothing
LOGS = {"logs"}  # read by everyone, depends on nothing (see logs/__init__.py)
# Formatting for a human reader, never a domain calculation: core is not
# allowed to do the former and forbidden from needing the latter, so this
# sits outside all four layers, same as config and logs.
HUMANIZE = {"humanize"}
# Catalogs, negotiation, and the Translator itself: read by
# core, adapters and entrypoints alike, same standing as config and logs.
I18N = {
    "i18n",
    "i18n.catalogs",
    "i18n.negotiation",
    "i18n.translator",
    "i18n.formatting",
    "i18n.jinja",
}
# The fourth layer: turns rows a route already read into what
# a template shows. Reaches into api.routes for RunSummary (see
# rendering.runs's own docstring on why that one import crosses into
# entrypoints). FORBIDDEN_FOR_CORE below only restrains core, so nothing
# here needs to forbid that.
RENDERING = {"rendering"}

LAYERS = {
    "core": CORE,
    "adapters": ADAPTERS,
    "entrypoints": ENTRYPOINTS,
    "config": CONFIG,
    "logs": LOGS,
    "humanize": HUMANIZE,
    "i18n": I18N,
    "rendering": RENDERING,
}

FORBIDDEN_FOR_CORE = {"adapters", "entrypoints"}


def module_name(path: Path) -> str:
    """Dotted module name of `path`, relative to the voxtrama package.

    The package root (src/voxtrama/__init__.py) maps to "": it only
    exposes __version__ and belongs to no layer, so it is exempt.
    """
    parts = list(path.relative_to(SRC_ROOT).parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts)


def classify(name: str) -> str | None:
    """Return the layer `name` belongs to, or None if unclassified.

    A module matches an entry if it equals it or is nested under it
    ("queue.job" under "queue"); the most specific (longest) match wins,
    so "queue.rq_backend" is an adapter even though "queue" is core.
    """
    matches = [
        (entry, layer)
        for layer, entries in LAYERS.items()
        for entry in entries
        if name == entry or name.startswith(entry + ".")
    ]
    if not matches:
        return None
    return max(matches, key=lambda pair: len(pair[0]))[1]


def voxtrama_modules() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))
