"""tuning.chunk_tuning: the Fine-tune panel's own arithmetic."""

from __future__ import annotations

from voxtrama.tuning.chunk_tuning import ChunkPlan, estimated_memory_gib


def test_total_cores_is_the_product_of_the_two_fields() -> None:
    plan = ChunkPlan(cores_per_chunk=8, parallel_chunks=2, recommended_parallel_chunks=2)

    assert plan.total_cores == 16


def test_asking_for_more_parallel_chunks_than_recommended_is_flagged() -> None:
    plan = ChunkPlan(cores_per_chunk=8, parallel_chunks=6, recommended_parallel_chunks=2)

    assert plan.exceeds_recommended is True


def test_estimated_memory_scales_with_parallel_chunks() -> None:
    plan = ChunkPlan(cores_per_chunk=8, parallel_chunks=2, recommended_parallel_chunks=2)
    one_gib = 1024**3

    gib = estimated_memory_gib(plan, model_download_bytes=one_gib)

    assert gib == 2.0
