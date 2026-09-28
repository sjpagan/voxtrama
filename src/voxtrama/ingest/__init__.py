"""Public surface of the ingest package.

The URL import (ingest.remote_url, yt-dlp) was removed: Voxtrama
transcribes files the person already has, and does not download audio
from third-party sites.
"""

from voxtrama.ingest.concat import concatenate_parts
from voxtrama.ingest.errors import UnsupportedMediaError
from voxtrama.ingest.local_file import import_local_file

__all__ = [
    "UnsupportedMediaError",
    "concatenate_parts",
    "import_local_file",
]
