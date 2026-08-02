#!/usr/bin/env bash
set -euo pipefail

BACKUP_MOUNT="/mnt/sdb2"
REPO_DIR="/home/javier14/Projects/masspropers-to-ebook"
OUTPUT_SRC="${REPO_DIR}/output"
OUTPUT_DEST="${BACKUP_MOUNT}/masspropers-output"
LOG_TAG="masspropers-backup"

log() {
	logger -t "$LOG_TAG" "$*"
	echo "$*"
}

# Ensure the backup drive is mounted, try to mount it if not
if ! mountpoint -q "$BACKUP_MOUNT"; then
	log "sdb2 not mounted, attempting mount"
	if ! mount "$BACKUP_MOUNT"; then
		log "ERROR: failed to mount $BACKUP_MOUNT, aborting backup"
		exit 1
	fi
fi

if ! mountpoint -q "$BACKUP_MOUNT"; then
	log "ERROR: $BACKUP_MOUNT still not mounted after mount attempt, aborting"
	exit 1
fi

if [ ! -d "$OUTPUT_SRC" ]; then
	log "ERROR: $OUTPUT_SRC does not exist, nothing to back up"
	exit 1
fi

mkdir -p "$OUTPUT_DEST"

log "starting output rsync"
if rsync -a --delete "$OUTPUT_SRC"/ "$OUTPUT_DEST"/; then
	log "output rsync succeeded"
else
	log "ERROR: output rsync failed"
	exit 1
fi

log "backup complete"
