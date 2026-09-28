"""Every download of a concluded job under one router.

The manifest to share, the transcript as a file, and the whole package:
registered together so api.app lists one line for the job's Files tab.
"""

from __future__ import annotations

from fastapi import APIRouter

from voxtrama.api.routes.job_files import router as job_files_router
from voxtrama.api.routes.job_package import router as job_package_router
from voxtrama.api.routes.run_manifest_export import router as manifest_router

router = APIRouter()
router.include_router(manifest_router)
router.include_router(job_files_router)
router.include_router(job_package_router)
