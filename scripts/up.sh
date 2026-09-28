#!/bin/sh
# `make up`'s script: brings the stack up on a free host port and only
# prints the URL once `web` answers, not once it has merely
# started.
#
# Stays on `sh`, like first-run-check.sh: `set -o pipefail` is
# a bash-ism this script does not need.
set -e

# `make up` always runs from the repo root, but someone running this
# script by hand from scripts/ should not have to know that: .env and
# `docker compose` both need to be found from the root. Move there first,
# from the script's own location, before touching either.
SCRIPT_DIR=$(dirname -- "$0")
cd "$SCRIPT_DIR/.." || exit 1

echo "=== 1. host port ==="
# Whoever already set VOXTRAMA_HOST_PORT (in the shell or in .env)
# chose it deliberately. Overriding it because a "better" port turned up
# would be worse than doing nothing.
if [ -z "${VOXTRAMA_HOST_PORT:-}" ] && [ -f .env ]; then
    # Strip an inline comment and surrounding whitespace: `VOXTRAMA_HOST_PORT=8080  # busy elsewhere`
    # must yield "8080", not "8080  # busy elsewhere".
    ENV_PORT=$(grep -E '^VOXTRAMA_HOST_PORT=' .env | tail -n1 | cut -d= -f2- |
        sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    if [ -n "$ENV_PORT" ]; then
        case "$ENV_PORT" in
            *[!0-9]*)
                echo "VOXTRAMA_HOST_PORT in .env is not a number: '$ENV_PORT'" >&2
                exit 1
                ;;
        esac
        VOXTRAMA_HOST_PORT="$ENV_PORT"
    fi
fi

if [ -n "${VOXTRAMA_HOST_PORT:-}" ]; then
    echo "VOXTRAMA_HOST_PORT already set to $VOXTRAMA_HOST_PORT, using it as-is"
else
    # python3's socket module binds a real socket and releases it, which
    # is portable between macOS and Linux. `nc -z` is not: BSD nc
    # (macOS) and GNU nc (Linux) disagree on what -z does, and neither is
    # guaranteed to be installed. 8000 stays the default when it is free,
    # so a bookmarked address does not change for no reason.
    VOXTRAMA_HOST_PORT=$(python3 - <<'PY'
import socket

port = 8000
while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            port += 1
            continue
    print(port)
    break
PY
)
    echo "port $VOXTRAMA_HOST_PORT is free, using it"
fi
export VOXTRAMA_HOST_PORT

echo "=== 2. docker compose up ==="
# The port checked above can be taken by someone else before
# `docker compose up` binds it, though the window between the
# check and the bind is short. That race is not worth closing with a retry: if
# it is lost, `docker compose up` fails on its own with a clear bind
# error, which is a better outcome than silently trying another port.
docker compose up -d

echo "=== 3. waiting for web to answer ==="
# The Dockerfile's HEALTHCHECK runs *inside* the container against
# 127.0.0.1:8000 *there*. It proves the process answers to itself, not
# that the *published* port on the host is mapped correctly, which is the
# one fact this script exists to check. It also only updates every 30s
# (interval=30s in the Dockerfile), which would leave the terminal frozen
# well after the server is reachable. Poll the host-side URL
# instead: the same one printed below, so it is only printed once true.
# `curl -fsS` is already a dependency of this repo (see `make
# sass-install`), so requiring it here costs nothing extra.
URL="http://127.0.0.1:${VOXTRAMA_HOST_PORT}/health"
TIMEOUT=180
WAITED=0
while true; do
    # A container that has already exited will never answer: stop now
    # with the real cause instead of waiting out the full timeout to say
    # "did not respond" about a process that is not even running.
    if [ -z "$(docker compose ps -q web)" ]; then
        echo "the 'web' container is not running, see: docker compose logs web" >&2
        exit 1
    fi
    if curl -fsS -o /dev/null "$URL" 2>/dev/null; then
        break
    fi
    if [ "$WAITED" -ge "$TIMEOUT" ]; then
        echo "web did not answer at $URL within ${TIMEOUT}s" >&2
        echo "see what's wrong with: docker compose logs web" >&2
        exit 1
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

echo "=== 4. ready ==="
echo "http://127.0.0.1:${VOXTRAMA_HOST_PORT}"
echo "follow the logs with: docker compose logs -f"
echo "stop the stack with: make down (or docker compose down)"
