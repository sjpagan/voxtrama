# Throwaway image for the diarization bench. Not part of the
# Voxtrama product image (that Dockerfile lives at the repo root): this one
# exists only to run tools/eval/bench.py and gets discarded afterwards.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg: some fixture/real-world clips need transcoding before either
# backend can read them. libsndfile1: soundfile's native dependency.
# build-essential: resemblyzer pulls in webrtcvad, which ships no wheel and
# has to be compiled from source. The published alternative is a third-party
# repackaging, and this project does not depend on unofficial republications
# of someone else's code, the same reason the pyannote weight mirrors
# were rejected. A compiler in a throwaway build image is the cheaper price.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        ca-certificates \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU wheels only: the bench compares two backends on the hardware a
# self-hosted Voxtrama instance actually has (the default target),
# not on a GPU most users won't have.
# torch and torchaudio come from the same index in the same command on
# purpose. speechbrain imports torchaudio, and letting pip pull that one from
# PyPI afterwards installs a build compiled against a different torch ABI:
# the import then dies on `Could not load this library: _torchaudio.abi3.so`,
# which reads like a broken install rather than a version mismatch.
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

RUN pip install \
    speechbrain \
    resemblyzer \
    scikit-learn \
    soundfile \
    scipy \
    numpy \
    pytest

COPY backends ./backends
COPY metrics.py rttm.py bench.py ./

# No HF_TOKEN build arg, no ~/.cache/huggingface bind mount: this is a
# constraint of the bench, not an oversight. speechbrain/spkrec-ecapa-voxceleb
# is a public model and must download with no Hugging Face account at all,
# because the bench has to be reproducible by anyone who clones the repo,
# not only by whoever already has a token configured.
ENTRYPOINT ["python", "bench.py"]
