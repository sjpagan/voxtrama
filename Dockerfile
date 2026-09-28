# Single image for web, worker and migrate. The comment that stood
# here said a second build target "would only differ by command:, since torch
# is not yet a dependency", and diarisation has just made it
# one. The image goes from 1.51 GB to 3.01 GB, and `web` and `migrate` carry
# the whole embedding stack to run code they never execute. Splitting the
# image is a decision, not a detail, so it is not taken here.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        ca-certificates \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# ffmpeg is here for ffprobe: ingest uses it to read a file's duration
# and format, and to tell "not a format we handle" apart from "not audio at
# all". ffmpeg itself is not invoked: no conversion happens.

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin voxtrama

WORKDIR /app

COPY pyproject.toml README.md alembic.ini requirements.lock ./
COPY src ./src
COPY migrations ./migrations
# The domain documents we ship (workflows, generative skill files, the
# generative model table, and the tuning files picked by machine).
# They are files of the package, read-only: nothing writes here,
# and a user's own live in the data directory instead, where a backup picks
# them up.
#
# All four lines matter, and skills/ was once missing: the runtime looks
# for a document under the working directory (/app here), and the package's own
# copy is no help once pip has installed it into site-packages, where no
# workflows/, skills/, model-catalog/ or tuning/ sits beside it. Without this
# line the image has no generative skills at all (BUILTIN_SKILLS came back as
# just transcribe and diarize), and every workflow naming one failed with
# "unknown skill". A folder added to workflow.document.DOMAIN_DOCUMENT_FOLDERS
# needs a COPY here too; the test in tests/test_packaging_documents.py fails if
# one is forgotten. model-catalog/, not models/: $VOXTRAMA_DATA_DIR/models is a
# third-party weights cache, not ours to put a hand-edited document in.
COPY workflows ./workflows
COPY skills ./skills
COPY model-catalog ./model-catalog
COPY tuning ./tuning
# The demo's audio. `voxtrama demo` must work without asking
# anyone to find a file, and the fixture the tests already use is the file to
# use: one file, two purposes. It is copied out of tests/ rather
# than duplicated in the repository: the image installs the package, it does
# not carry the test suite.
COPY tests/fixtures/public-fixture.wav ./demo/public-fixture.wav

# Every library at the version requirements.lock pins, so two builds of
# the same commit install the same code. The lock names PyTorch's CPU index
# and pins torch/torchaudio to its +cpu builds: the PyPI wheels carry CUDA
# and weigh several gigabytes on a machine that will never have a GPU.
# The package itself goes in with --no-deps, so
# nothing pyproject's ranges allow can move a pinned version.
RUN pip install -r requirements.lock
RUN pip install --no-deps .

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# No model weights, no data: those live on the bind-mounted VOXTRAMA_DATA_DIR,
# never inside the image.

HEALTHCHECK --start-period=60s --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# The web service's command; migrate and worker override it in compose.yaml.
CMD ["gunicorn", "voxtrama.api.app:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "1", \
     "--timeout", "120", \
     "--bind", "0.0.0.0:8000"]
