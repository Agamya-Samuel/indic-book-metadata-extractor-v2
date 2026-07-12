#!/bin/bash
set -e

GADGETS_DIR="/gadgets"
mkdir -p "$GADGETS_DIR"

WIKIDATA_API="https://www.wikidata.org/w/api.php"

GADGET_PAGES=(
    "MediaWiki:Gadget-Merge.js"
    "MediaWiki:Gadget-labelLister.js"
    "MediaWiki:Gadget-KeyShortcuts.js"
    "MediaWiki:Gadget-DuplicateReferences.js"
    "MediaWiki:Gadget-DuplicateReferences.css"
    "MediaWiki:Gadget-compact items.css"
    "MediaWiki:Gadget-NarrowUI.css"
    "MediaWiki:Gadget-Descriptions.js"
    "MediaWiki:Gadget-AuthorityControl.js"
)

echo "[fetch-gadgets] Fetching gadget source files from wikidata.org..."

for PAGE in "${GADGET_PAGES[@]}"; do
    FILENAME=$(echo "$PAGE" | sed 's/MediaWiki:Gadget-//')
    echo -n "  Fetching ${PAGE}... "

    ENCODED_PAGE=$(echo "$PAGE" | sed 's/ /_/g')
    RESULT=$(curl -s --max-time 30 \
        "${WIKIDATA_API}?action=query&titles=${ENCODED_PAGE}&prop=revisions&rvprop=content&format=json&rvslots=main")

    CONTENT=$(echo "$RESULT" | jq -r '.query.pages | to_entries[0].value.revisions[0].slots.main["*"] // empty')

    if [ -n "$CONTENT" ] && [ "$CONTENT" != "null" ]; then
        echo "$CONTENT" > "${GADGETS_DIR}/${FILENAME}"
        echo "OK ($(echo "$CONTENT" | wc -c) bytes)"
    else
        echo "FAILED (page not found or empty)"
    fi
done

echo "[fetch-gadgets] Done. Fetched files saved to ${GADGETS_DIR}/"
ls -la "${GADGETS_DIR}/"
