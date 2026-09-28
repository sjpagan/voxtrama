#!/bin/sh
# The alpha's end-to-end check:
# from a clone, with an untouched .env and a data directory that does
# not exist yet, to a finished job, without configuring anything.
#
# "Without configuring anything" means no hardware profile is set here, so the machine's proposal
# (proposal.toml) is what runs. The transcription model is downloaded the
# way the home page's first-run card does it, the job is posted the way the
# new-job form posts it, and the check ends by reading voxtrama.toml, which
# the first finished job writes with the values it used.
#
# CHECK_AUDIO picks the file (default: the demo's real recording) and
# CHECK_WORKFLOW the workflow (default: transcribe-only). A workflow with a
# generative step, meeting-decisions for one, needs a model server the
# stack can reach: pass it when there is one.
#
# Whatever this script starts, it stops: `docker compose down` runs
# on every exit, success or failure. CHECK_KEEP=1 leaves the stack up to
# look at it, and then stopping it is on whoever asked.
#
# Stays on `sh`: `set -o pipefail` is a bash-ism, and this script
# has no other reason to need bash. Where a pipeline's exit status matters
# (step 3), the output is captured to a file and the real status is checked
# before the file is read.
set -e

DATA_DIR=${CHECK_DATA_DIR:-/tmp/voxtrama-alpha-check}
export VOXTRAMA_DATA_DIR=$DATA_DIR
unset VOXTRAMA_HARDWARE_PROFILE VOXTRAMA_CORES_PER_CHUNK VOXTRAMA_PARALLEL_CHUNKS
AUDIO=${CHECK_AUDIO:-tests/fixtures/public-fixture.wav}
WORKFLOW=${CHECK_WORKFLOW:-transcribe-only}
# Same variable the compose file reads, so whoever already has 8000
# taken by something else can run the check without shutting it down.
VOXTRAMA_HOST_PORT=${VOXTRAMA_HOST_PORT:-8000}
export VOXTRAMA_HOST_PORT
URL="http://127.0.0.1:$VOXTRAMA_HOST_PORT"

rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"

STARTED=""
stop_stack() {
    if [ -n "$STARTED" ] && [ "${CHECK_KEEP:-0}" != "1" ]; then
        echo "=== stopping the stack ==="
        docker compose down >/dev/null 2>&1 || true
    fi
    # Step 1 needs an untouched .env. The one that was here comes back.
    if [ -f .env.before-check ]; then
        mv .env.before-check .env
    fi
}
trap stop_stack EXIT INT TERM

# Polls `$1` (a shell test) every 5 seconds, up to `$2` seconds. `$3` names
# what is awaited when it never comes.
wait_for() {
    waited=0
    until sh -c "$1"; do
        waited=$((waited + 5))
        if [ "$waited" -ge "$2" ]; then
            echo "gave up waiting for $3 after $2 s" >&2
            exit 1
        fi
        sleep 5
    done
}

echo "=== 1. cp .env.example .env (untouched) ==="
# An .env already here is someone's configuration: set aside, put back on exit.
if [ -f .env ]; then
    mv .env .env.before-check
fi
cp .env.example .env
echo "done"

echo "=== 2. is the port free? ==="
# A bound port made `docker compose up` fail with a bind error that
# nothing downstream noticed, and the check limped on to `doctor` against a
# stack that never came up. Refuse to start instead of guessing, and name
# what is holding the port. The usual case is a container an agent forgot to
# stop, and the container's name is what closes that loop.
if ! command -v lsof >/dev/null 2>&1; then
    # A missing diagnostic tool is not a product defect: say we could not
    # look, do not refuse to run the check because of it.
    echo "lsof not found: could not check whether port $VOXTRAMA_HOST_PORT is free"
else
    LISTENER=$(lsof -nP -iTCP:"$VOXTRAMA_HOST_PORT" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1, $2}')
    if [ -n "$LISTENER" ]; then
        CONTAINER=$(docker ps --filter "publish=$VOXTRAMA_HOST_PORT" --format '{{.Names}}' 2>/dev/null | head -1)
        if [ -n "$CONTAINER" ]; then
            echo "port $VOXTRAMA_HOST_PORT is occupied by container '$CONTAINER'" >&2
        else
            echo "port $VOXTRAMA_HOST_PORT is occupied by process $LISTENER" >&2
        fi
        exit 1
    fi
fi

echo "=== 3. docker compose up ==="
# A plain pipe to `tail` hid `up`'s failure under `set -e`: in POSIX `sh` a
# pipeline's status is the last command's, and `tail` always succeeds. Write
# the full output to a file, check the real status, then show the tail.
UP_LOG=$(mktemp)
STARTED=1
if docker compose up -d --build >"$UP_LOG" 2>&1; then
    tail -3 "$UP_LOG"
    rm -f "$UP_LOG"
else
    tail -20 "$UP_LOG"
    rm -f "$UP_LOG"
    echo "docker compose up failed, see the output above" >&2
    exit 1
fi

echo "=== 4. the machine's proposal is written and declared ==="
wait_for "curl -fs $URL/health >/dev/null" 180 "the web service"
test -f "$DATA_DIR/proposal.toml" || { echo "no proposal.toml in $DATA_DIR" >&2; exit 1; }
grep -v '^#' "$DATA_DIR/proposal.toml" | sed '/^$/d'
test ! -f "$DATA_DIR/voxtrama.toml" || { echo "voxtrama.toml before any job" >&2; exit 1; }
curl -fs "$URL/" | grep -q "Proposed for this machine" || {
    echo "the home page does not declare the proposal" >&2; exit 1; }
echo "declared on the home page"

echo "=== 5. voxtrama doctor ==="
docker compose exec -T web voxtrama doctor

echo "=== 6. the transcription model, downloaded from the home page's card ==="
PROFILE=$(sed -n 's/^hardware_profile = "\(.*\)"/\1/p' "$DATA_DIR/proposal.toml")
CORES=$(sed -n 's/^cores_per_chunk = //p' "$DATA_DIR/proposal.toml")
PARALLEL=$(sed -n 's/^parallel_chunks = //p' "$DATA_DIR/proposal.toml")
curl -fs -o /dev/null -X POST "$URL/setup/local-processing" \
    -d "hardware_profile=$PROFILE" -d "cores_per_chunk=$CORES" \
    -d "parallel_chunks=$PARALLEL" -d "return_to=/"
wait_for "curl -fs $URL/ | grep -q 'Start job'" 1800 "the model download"
echo "the home page offers Start job"

echo "=== 7. a job, posted the way the new-job form posts it ==="
RUN_URL=$(curl -fs -o /dev/null -w '%{redirect_url}' -X POST "$URL/jobs" \
    -F "files=@$AUDIO" -F "workflow_name=$WORKFLOW" -F "label=alpha check")
RUN_ID=$(echo "$RUN_URL" | sed -n 's|.*/runs/\([^/]*\)/view|\1|p')
test -n "$RUN_ID" || { echo "the job was not created: $RUN_URL" >&2; exit 1; }
echo "run $RUN_ID ($WORKFLOW)"
# The run's own state, not a step's: steps carry a "state" key too.
STATE_CMD="curl -fs $URL/runs/$RUN_ID | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"state\"])'"
wait_for "$STATE_CMD | grep -qE '^(succeeded|failed|cancelled|interrupted)$'" 1800 "the job"
STATE=$(sh -c "$STATE_CMD")
echo "state: $STATE"
test "$STATE" = "succeeded" || { curl -fs "$URL/runs/$RUN_ID"; exit 1; }

echo "=== 8. voxtrama.toml, written by the first job with what it used ==="
wait_for "test -f $DATA_DIR/voxtrama.toml" 30 "voxtrama.toml"
grep -E '^(hardware_profile|cores_per_chunk|parallel_chunks) ' "$DATA_DIR/voxtrama.toml"
test ! -f "$DATA_DIR/proposal.toml" || { echo "proposal.toml still there" >&2; exit 1; }
if curl -fs "$URL/" | grep -q "Proposed for this machine"; then
    echo "the home page still shows the proposal" >&2; exit 1
fi

echo "=== 9. what landed in the database ==="
docker compose exec -T web python3 - <<'PY'
import sqlite3

connection = sqlite3.connect("/data/voxtrama.db")
for row in connection.execute("select id, state from run order by rowid desc limit 1"):
    print("RUN", row[0][:8], row[1])
for row in connection.execute("select step_id, state from run_step"):
    print(" STEP", row[0], row[1])
query = "select language, model_name, hardware_profile, cpu_threads, num_workers from transcript"
for row in connection.execute(query):
    print("TRANSCRIPT", row)
query = "select coalesce(speaker_label, '-'), substr(text, 1, 44) from segment order by start"
for row in connection.execute(query):
    print("  ", row[0], row[1])
PY

echo "=== the alpha check passed ==="
