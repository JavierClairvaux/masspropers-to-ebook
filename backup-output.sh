#!/usr/bin/env bash
# Rsyncs the masspropers-to-ebook output directory over the tailnet to both
# encrypted disks on cabfam-ser (/mnt/backup1 and /mnt/backup2), instead of
# a local disk on this box.
#
# Requires: passwordless SSH (key-based) from media-backup to
# jca14@cabfam-ser for this cron job to run non-interactively.
set -euo pipefail

REPO_DIR="/home/javier14/Projects/masspropers-to-ebook"
OUTPUT_SRC="${REPO_DIR}/output"
LOG_TAG="masspropers-backup"

REMOTE_USER="jca14"
REMOTE_HOST="cabfam-ser"
REMOTE_TARGETS=("/mnt/backup1" "/mnt/backup2")

log() {
    logger -t "$LOG_TAG" "$*"
    echo "$*"
}

if [ ! -d "$OUTPUT_SRC" ]; then
    log "ERROR: $OUTPUT_SRC does not exist, nothing to back up"
    exit 1
fi

# Confirm cabfam-ser is reachable over the tailnet before doing any work
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "${REMOTE_USER}@${REMOTE_HOST}" true; then
    log "ERROR: cannot reach ${REMOTE_USER}@${REMOTE_HOST} over ssh, aborting backup"
    exit 1
fi

for TARGET in "${REMOTE_TARGETS[@]}"; do
    REMOTE_DEST="${TARGET}/masspropers-output"

    log "ensuring remote dir exists on ${REMOTE_HOST}:${REMOTE_DEST}"
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_DEST}'"

    log "starting output rsync to ${REMOTE_HOST}:${REMOTE_DEST}"
    if rsync -a --delete -e ssh "$OUTPUT_SRC"/ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DEST}"/; then
        log "output rsync to ${TARGET} succeeded"
    else
        log "ERROR: output rsync to ${TARGET} failed"
        exit 1
    fi
done

log "backup complete"
