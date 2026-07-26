#!/usr/bin/env bash
# Generates the EPUB for tomorrow's Mass Propers and hands it to
# Calibre-Web-Automated's ingest folder for auto-import. Intended to run
# Saturday evening via cron, so "tomorrow" resolves to Sunday.
#
# Note: CWA deletes files from /cwa-book-ingest after importing them, so the
# permanent copy lives in output/ (masspropers' own dir) — we COPY into
# ingest, we don't move, and we copy-then-rename so CWA never sees a
# partially-written file.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INGEST_DIR="${REPO_DIR}/calibre-web/ingest"
cd "$REPO_DIR"

TARGET_DATE="$(date -d tomorrow +%Y-%m-%d)"

echo "[$(date -Is)] Generating propers for ${TARGET_DATE}"
python3 -m masspropers.cli "${TARGET_DATE}"

# Pick the most recently created .epub in output/ — this is the file the
# `masspropers.cli` invocation above just wrote, regardless of how its
# filename is slugged.
EPUB_PATH="$(find output -maxdepth 1 -name "*.epub" -printf '%T@ %p\n' \
    | sort -n | tail -n1 | cut -d' ' -f2-)"

if [ -z "${EPUB_PATH:-}" ]; then
    echo "[$(date -Is)] ERROR: no output EPUB found in output/" >&2
    exit 1
fi

BASENAME="$(basename "$EPUB_PATH")"
TMP_DEST="${INGEST_DIR}/.${BASENAME}.partial"
FINAL_DEST="${INGEST_DIR}/${BASENAME}"

cp "$EPUB_PATH" "$TMP_DEST"
mv "$TMP_DEST" "$FINAL_DEST"   # atomic rename — CWA never sees a partial file

echo "[$(date -Is)] Handed off ${BASENAME} to Calibre-Web-Automated ingest."
echo "[$(date -Is)] Done."
