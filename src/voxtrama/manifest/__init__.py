"""The run manifest: how a run was executed, archived once it starts.

`progress.json` (engine.progress_file) and `manifest.json` are two files with
two different jobs, and neither replaces the other. progress.json says what
is happening right now and is ephemeral: the next write overwrites it, and
nothing keeps the old ones. manifest.json says how the run was executed
(input, environment, every step, determinism) and is meant to be
archived, diffed against another run, and read back long after the run
that wrote it has finished.

This module is deliberately not part of engine: other code reads a
manifest (comparing two, serving one over the API, building a gold
dataset from many), and none of them needs the engine that produced it.
Tying them to it would be the wrong dependency for a file the engine only
produces, never reads back.

`schema.py` declares the shape as Pydantic models; `writer.py` builds one
from a Run and writes it atomically. Nothing here executes a workflow.
"""

from __future__ import annotations
