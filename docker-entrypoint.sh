#!/bin/sh
# Starts as root, aligns ownership of the mounted data directory with the
# unprivileged `voxtrama` user, then execs the given command as that user.
set -e

VOXTRAMA_DATA_DIR="${VOXTRAMA_DATA_DIR:-/data}"
APP_USER=voxtrama

die() {
    echo "docker-entrypoint: $1" >&2
    exit 1
}

# --- the data directory must be mounted and writable ----------------------

[ -d "$VOXTRAMA_DATA_DIR" ] || die "$VOXTRAMA_DATA_DIR does not exist inside the container. Mount your data directory there. See compose.yaml and VOXTRAMA_DATA_DIR in .env.example."

if ! touch "$VOXTRAMA_DATA_DIR/.voxtrama-write-test" 2>/dev/null; then
    die "$VOXTRAMA_DATA_DIR is not writable. Check the permissions of the host folder it is bind-mounted from."
fi
rm -f "$VOXTRAMA_DATA_DIR/.voxtrama-write-test"

# --- align the app user with the host ownership of the data directory -----
#
# usermod/groupmod change the identity of `voxtrama` itself, once, so every
# file the process writes from here on lands with the right owner without
# a recursive chown of a directory that will hold large audio files. A
# chown limited to "the directories we create" would leave files from a
# previous run under a stale uid untouched; changing the user's identity
# does not have that gap.

# An explicit override wins over auto-detection: it covers the cases the
# data directory cannot reveal: extra roots owned by someone else, network
# mounts whose reported ownership is not the effective one, or a server that
# must write as a specific service account.
host_uid="${VOXTRAMA_RUN_AS_UID:-$(stat -c %u "$VOXTRAMA_DATA_DIR")}"
host_gid="${VOXTRAMA_RUN_AS_GID:-$(stat -c %g "$VOXTRAMA_DATA_DIR")}"
app_uid=$(id -u "$APP_USER")
app_gid=$(id -g "$APP_USER")

if [ "$host_uid" = "0" ] && [ -z "${VOXTRAMA_RUN_AS_UID:-}" ]; then
    # Docker created the host folder as root because it did not exist yet
    # (common on Linux, first run). It is empty, so claiming it is a single
    # non-recursive chown, not the blind recursion we avoid below.
    # Only if it really is empty: a root-owned
    # folder with files in it is someone else's, typed by mistake as the
    # data folder, and must not change owner.
    if [ -n "$(ls -A "$VOXTRAMA_DATA_DIR")" ]; then
        die "$VOXTRAMA_DATA_DIR belongs to root and is not empty. Choose another data folder, or set VOXTRAMA_RUN_AS_UID and VOXTRAMA_RUN_AS_GID."
    fi
    chown "$APP_USER:$APP_USER" "$VOXTRAMA_DATA_DIR"
else
    if [ "$host_uid" != "$app_uid" ]; then
        # No -m here: usermod refuses it without -d ("-m flag is only allowed
        # with the -d flag"), which would abort the container on the most
        # common Linux first run. -u alone already re-owns the home directory.
        usermod -u "$host_uid" "$APP_USER" || die "could not align voxtrama's uid to $host_uid."
    fi
    if [ "$host_gid" != "$app_gid" ]; then
        groupmod -g "$host_gid" "$APP_USER" || die "could not align voxtrama's gid to $host_gid."
    fi
fi

# --- create the data directory's subdirectories, owned by the app user ----

for dir in recordings runs models logs; do
    target="$VOXTRAMA_DATA_DIR/$dir"
    if [ ! -d "$target" ]; then
        mkdir -p "$target"
        chown "$APP_USER:$APP_USER" "$target"
    fi
done

# --- drop privileges and exec the given command ----------------------------
#
# setpriv, not gosu: util-linux ships it already on python:3.11-slim, so
# dropping privileges costs no extra package and no binary fetched at
# build time.
#
# HOME is set explicitly because setpriv does not: it changes the uid and
# leaves the environment alone, so HOME would stay /root (root's home, which
# the user we just became cannot write). Both model libraries write under
# ~/.cache before honouring any download directory we pass them, and the
# failure reads "Permission denied: /root/.cache/huggingface/token", which
# says nothing about the real cause.

export HOME="/home/$APP_USER"

exec setpriv --reuid "$APP_USER" --regid "$APP_USER" --init-groups "$@"
