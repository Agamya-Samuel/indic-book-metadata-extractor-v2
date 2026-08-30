#!/bin/bash
set -e

GADGETS_DIR="/gadgets"
MW_ADMIN_NAME="${MW_ADMIN_NAME:-admin}"
MW_ADMIN_PASS="${MW_ADMIN_PASS:-admin}"
MW_WG_SERVER="${MW_WG_SERVER:-http://localhost:8181}"
MW_API="${MW_WG_SERVER}/w/api.php"

echo "[install-gadgets] Waiting for Wikibase API..."
for i in $(seq 1 60); do
    if curl -s -o /dev/null -w '%{http_code}' "${MW_API}?action=query&format=json" | grep -q '200'; then
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "[install-gadgets] ERROR: API not available after 5 minutes."
        exit 1
    fi
    sleep 5
done

echo "[install-gadgets] Logging in..."
LOGIN_TOKEN=$(curl -s -c /tmp/gad_cookies -b /tmp/gad_cookies \
    "${MW_API}?action=query&meta=tokens&type=login&format=json" | \
    jq -r '.query.tokens.logintoken')

curl -s -c /tmp/gad_cookies -b /tmp/gad_cookies \
    -d "action=login&lgname=${MW_ADMIN_NAME}&lgpassword=${MW_ADMIN_PASS}&lgtoken=${LOGIN_TOKEN}&format=json" \
    "${MW_API}" > /dev/null

CSRF_TOKEN=$(curl -s -c /tmp/gad_cookies -b /tmp/gad_cookies \
    "${MW_API}?action=query&meta=tokens&format=json" | \
    jq -r '.query.tokens.csrftoken')

if [ "$CSRF_TOKEN" = "null" ] || [ -z "$CSRF_TOKEN" ]; then
    echo "[install-gadgets] ERROR: Failed to get CSRF token."
    exit 1
fi

create_page() {
    local title="$1"
    local file="$2"
    local summary="$3"

    if [ ! -f "$file" ]; then
        echo "  SKIP ${title} (file not found: ${file})"
        return
    fi

    CONTENT=$(cat "$file")
    echo -n "  Creating ${title}... "

    RESULT=$(curl -s -c /tmp/gad_cookies -b /tmp/gad_cookies \
        --data-urlencode "action=edit" \
        --data-urlencode "title=${title}" \
        --data-urlencode "text=${CONTENT}" \
        --data-urlencode "summary=${summary}" \
        --data-urlencode "token=${CSRF_TOKEN}" \
        --data-urlencode "format=json" \
        "${MW_API}")

    if echo "$RESULT" | jq -e '.edit.result' > /dev/null 2>&1; then
        echo "OK"
    else
        ERROR=$(echo "$RESULT" | jq -r '.error.info // "unknown"')
        echo "FAILED: ${ERROR}"
    fi
}

echo "[install-gadgets] Creating Gadgets definition page..."
DEFINITION='* Merge[ResourceLoader|namespaces=0]|Gadget-Merge.js
* labelLister[ResourceLoader|namespaces=0,120]|Gadget-labelLister.js
* KeyShortcuts[ResourceLoader]|Gadget-KeyShortcuts.js
* DuplicateReferences[ResourceLoader]|Gadget-DuplicateReferences.js|Gadget-DuplicateReferences.css
* compact items[ResourceLoader]|Gadget-compact items.css
* NarrowUI[ResourceLoader]|Gadget-NarrowUI.css
* Descriptions[ResourceLoader]|Gadget-Descriptions.js
* AuthorityControl[ResourceLoader]|Gadget-AuthorityControl.js'

RESULT=$(curl -s -c /tmp/gad_cookies -b /tmp/gad_cookies \
    --data-urlencode "action=edit" \
    --data-urlencode "title=MediaWiki:Gadgets-definition" \
    --data-urlencode "text=${DEFINITION}" \
    --data-urlencode "summary=Install curated Wikidata gadgets" \
    --data-urlencode "token=${CSRF_TOKEN}" \
    --data-urlencode "format=json" \
    "${MW_API}")

if echo "$RESULT" | jq -e '.edit.result' > /dev/null 2>&1; then
    echo "  MediaWiki:Gadgets-definition... OK"
else
    echo "  MediaWiki:Gadgets-definition... FAILED"
fi

echo "[install-gadgets] Creating gadget source pages..."
create_page "MediaWiki:Gadget-Merge.js" "${GADGETS_DIR}/Merge.js" "Install Merge gadget"
create_page "MediaWiki:Gadget-labelLister.js" "${GADGETS_DIR}/labelLister.js" "Install labelLister gadget"
create_page "MediaWiki:Gadget-KeyShortcuts.js" "${GADGETS_DIR}/KeyShortcuts.js" "Install KeyShortcuts gadget"
create_page "MediaWiki:Gadget-DuplicateReferences.js" "${GADGETS_DIR}/DuplicateReferences.js" "Install DuplicateReferences gadget"
create_page "MediaWiki:Gadget-DuplicateReferences.css" "${GADGETS_DIR}/DuplicateReferences.css" "Install DuplicateReferences styles"
create_page "MediaWiki:Gadget-compact items.css" "${GADGETS_DIR}/compact items.css" "Install compact items gadget"
create_page "MediaWiki:Gadget-NarrowUI.css" "${GADGETS_DIR}/NarrowUI.css" "Install NarrowUI gadget"
create_page "MediaWiki:Gadget-Descriptions.js" "${GADGETS_DIR}/Descriptions.js" "Install Descriptions gadget"
create_page "MediaWiki:Gadget-AuthorityControl.js" "${GADGETS_DIR}/AuthorityControl.js" "Install AuthorityControl gadget"

echo "[install-gadgets] Done. Gadgets installed. Enable them at Special:Preferences#mw-prefsection-gadgets"
