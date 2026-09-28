"""The fine-tune numbers a person can see and correct.

tuning.selector already proposes cores_per_chunk and parallel_chunks for
this machine. This module only does the arithmetic the "Fine-tune" panel
shows under the two fields it lets someone change. That is the ASR profile's rule
applied to chunking instead of the ASR profile: propose, then show the
numbers instead of hiding them. Whether the chosen parallel_chunks exceeds
what the tuning file recommends is decided elsewhere, restated here only
as a boolean: going over is allowed, it is a warning, not a cap.

`estimated_memory_gib` has no measured formula behind it anywhere in this
codebase: "how much the machine can sustain" is left to the machine's
memory reading, with no per-chunk cost worked out for any model, and
tuning/*.yaml's `chunking.memory.recommended_gib` is a whole-machine
recommendation, not a per-chunk one. The number below is the closest thing
that exists: the selected ASR model's nominal download size
(transcription.asr.weights_for) times parallel_chunks. It lands close
to the one real figure available (a measured "~2.7 GB per
chunk with large models" for large-v3). It is a placeholder standing in
for a measurement nobody has taken yet, named as one so it is not mistaken
for the machine's own memory readings.
"""

from __future__ import annotations

from dataclasses import dataclass

GIB = 1024**3


@dataclass(frozen=True)
class ChunkPlan:
    """cores_per_chunk and parallel_chunks, and what they add up to."""

    cores_per_chunk: int
    parallel_chunks: int
    recommended_parallel_chunks: int
    # What the machine physically has. Asking for more asks for something
    # that is not there, the same distinction drawn for num_ctx above a
    # model's own maximum. The *memory* limit stays a
    # warning because beyond it there is a cost (swap, slowness) and still an
    # outcome. Beyond the cores that exist there is no outcome, so this is a cap.
    available_cores: int | None = None

    @property
    def total_cores(self) -> int:
        return self.cores_per_chunk * self.parallel_chunks

    @property
    def exceeds_available(self) -> bool:
        return self.available_cores is not None and self.total_cores > self.available_cores

    @property
    def exceeds_recommended(self) -> bool:
        return self.parallel_chunks > self.recommended_parallel_chunks


def estimated_memory_gib(chunk_plan: ChunkPlan, model_download_bytes: int) -> float:
    """ESTIMATE (see module docstring): parallel_chunks times one model's own size."""
    return chunk_plan.parallel_chunks * (model_download_bytes / GIB)
