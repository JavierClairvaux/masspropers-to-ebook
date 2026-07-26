#!/usr/bin/env bash
# Generates both language editions (es, en) of tomorrow's Mass Propers and
# hands each off to Calibre-Web-Automated's ingest folder for auto-import.
# Intended to run Saturday evening via cron, so "tomorrow" resolves to Sunday.
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

for LANG in es en; do
    echo "[$(date -Is)] Generating propers for ${TARGET_DATE} (--lang ${LANG})"

    # Capture the exact path from the CLI's own "Wrote <path>" line rather
    # than guessing by mtime — necessary now that two files get written in
    # the same run, so "most recently created" would be ambiguous/wrong for
    # the first of the two.
    OUT_LINE="$(python3 -m masspropers.cli "${TARGET_DATE}" --lang "${LANG}" | tee /dev/stderr | grep '^Wrote ')"
    EPUB_PATH="${OUT_LINE#Wrote }"

    if [ -z "${EPUB_PATH:-}" ] || [ ! -f "$EPUB_PATH" ]; then
        echo "[$(date -Is)] ERROR: no output EPUB found for ${TARGET_DATE} (--lang ${LANG})" >&2
        exit 1
    fi

    BASENAME="$(basename "$EPUB_PATH")"
    TMP_DEST="${INGEST_DIR}/.${BASENAME}.partial"
    FINAL_DEST="${INGEST_DIR}/${BASENAME}"

    cp "$EPUB_PATH" "$TMP_DEST"
    mv "$TMP_DEST" "$FINAL_DEST"   # atomic rename — CWA never sees a partial file

    echo "[$(date -Is)] Handed off ${BASENAME} to Calibre-Web-Automated ingest."
done

echo "[$(date -Is)] Done."
