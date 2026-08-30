#!/bin/bash
set -e

MW_ADMIN_NAME="${MW_ADMIN_NAME:-admin}"
MW_ADMIN_PASS="${MW_ADMIN_PASS:-admin}"
MW_WG_SERVER="${MW_WG_SERVER:-http://localhost:8181}"
PROPERTIES_FILE="/properties.json"
MAPPING_FILE="/config/property-mapping.json"
MW_API="${MW_WG_SERVER}/w/api.php"

echo "[create-properties] Waiting for Wikibase API to become available..."
for i in $(seq 1 60); do
    if curl -s -o /dev/null -w '%{http_code}' "${MW_API}?action=query&format=json" | grep -q '200'; then
        echo "[create-properties] API is ready."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "[create-properties] ERROR: API not available after 5 minutes. Exiting."
        exit 1
    fi
    sleep 5
done

echo "[create-properties] Logging in as ${MW_ADMIN_NAME}..."
LOGIN_TOKEN=$(curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
    "${MW_API}?action=query&meta=tokens&type=login&format=json" | \
    jq -r '.query.tokens.logintoken')

curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
    -d "action=login&lgname=${MW_ADMIN_NAME}&lgpassword=${MW_ADMIN_PASS}&lgtoken=${LOGIN_TOKEN}&format=json" \
    "${MW_API}" > /dev/null

CSRF_TOKEN=$(curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
    "${MW_API}?action=query&meta=tokens&format=json" | \
    jq -r '.query.tokens.csrftoken')

if [ "$CSRF_TOKEN" = "null" ] || [ -z "$CSRF_TOKEN" ]; then
    echo "[create-properties] ERROR: Failed to get CSRF token. Login may have failed."
    exit 1
fi

echo "[create-properties] Login successful."

# Check if mapping file already exists (idempotent)
if [ -f "$MAPPING_FILE" ]; then
    echo "[create-properties] Mapping file already exists at ${MAPPING_FILE}. Checking..."
    EXISTING_COUNT=$(jq 'length' "$MAPPING_FILE" 2>/dev/null || echo "0")
    if [ "$EXISTING_COUNT" -gt 0 ]; then
        echo "[create-properties] Found ${EXISTING_COUNT} existing mappings. Skipping creation."
        exit 0
    fi
fi

echo "[create-properties] Creating properties from ${PROPERTIES_FILE}..."
MAPPING="{"

PROP_COUNT=$(jq 'length' "$PROPERTIES_FILE")
for i in $(seq 0 $((PROP_COUNT - 1))); do
    WIKIDATA_ID=$(jq -r ".[$i].wikidata_id" "$PROPERTIES_FILE")
    LABEL=$(jq -r ".[$i].label" "$PROPERTIES_FILE")
    DATATYPE=$(jq -r ".[$i].datatype" "$PROPERTIES_FILE")
    DESCRIPTION=$(jq -r ".[$i].description" "$PROPERTIES_FILE")

    echo -n "  Creating ${WIKIDATA_ID} (${LABEL})... "

    # Check if property with this label already exists
    SEARCH_RESULT=$(curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
        "${MW_API}?action=wbsearchentities&search=$(echo "$LABEL" | sed 's/ /+/g')&language=en&type=property&format=json")
    EXISTING_ID=$(echo "$SEARCH_RESULT" | jq -r '.search[0].id // empty')

    if [ -n "$EXISTING_ID" ]; then
        echo "already exists as ${EXISTING_ID}"
        LOCAL_ID="$EXISTING_ID"
    else
        # Create property via wbcreateclaim API
        ENTITY_DATA="{\"labels\":{\"en\":{\"language\":\"en\",\"value\":\"${LABEL}\"}},\"descriptions\":{\"en\":{\"language\":\"en\",\"value\":\"${DESCRIPTION}\"}},\"datatype\":\"${DATATYPE}\"}"

        RESULT=$(curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
            --data-urlencode "action=wbeditentity" \
            --data-urlencode "new=property" \
            --data-urlencode "data=${ENTITY_DATA}" \
            --data-urlencode "token=${CSRF_TOKEN}" \
            --data-urlencode "format=json" \
            "${MW_API}")

        LOCAL_ID=$(echo "$RESULT" | jq -r '.entity.id // empty')
        if [ -n "$LOCAL_ID" ]; then
            echo "created as ${LOCAL_ID}"
        else
            ERROR_INFO=$(echo "$RESULT" | jq -r '.error.info // "unknown error"')
            echo "FAILED: ${ERROR_INFO}"
            continue
        fi
    fi

    # Build mapping
    if [ "$i" -gt 0 ]; then
        MAPPING="${MAPPING},"
    fi
    MAPPING="${MAPPING}\"${WIKIDATA_ID}\":\"${LOCAL_ID}\""
done

# Also create Q571 (book) item
echo -n "  Creating Q571 (book) item... "
SEARCH_RESULT=$(curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
    "${MW_API}?action=wbsearchentities&search=book&language=en&type=item&format=json")
BOOK_QID=$(echo "$SEARCH_RESULT" | jq -r '.search[0].id // empty')

if [ -n "$BOOK_QID" ]; then
    echo "already exists as ${BOOK_QID}"
else
    ENTITY_DATA='{"labels":{"en":{"language":"en","value":"book"}},"descriptions":{"en":{"language":"en","value":"written work published as a physical or digital book"}}}'
    RESULT=$(curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
        --data-urlencode "action=wbeditentity" \
        --data-urlencode "new=item" \
        --data-urlencode "data=${ENTITY_DATA}" \
        --data-urlencode "token=${CSRF_TOKEN}" \
        --data-urlencode "format=json" \
        "${MW_API}")
    BOOK_QID=$(echo "$RESULT" | jq -r '.entity.id // empty')
    if [ -n "$BOOK_QID" ]; then
        echo "created as ${BOOK_QID}"
    else
        echo "FAILED"
    fi
fi

if [ -n "$BOOK_QID" ]; then
    MAPPING="${MAPPING},\"Q571\":\"${BOOK_QID}\""
fi

MAPPING="${MAPPING}}"

echo "$MAPPING" | jq '.' > "$MAPPING_FILE"
echo "[create-properties] Property mapping written to ${MAPPING_FILE}"
echo "[create-properties] Done. Created $(echo "$MAPPING" | jq 'length') entity mappings."
