#!/bin/bash
set -e

MW_ADMIN_NAME="${MW_ADMIN_NAME:-admin}"
MW_ADMIN_PASS="${MW_ADMIN_PASS:-admin}"
MW_WG_SERVER="${MW_WG_SERVER:-http://localhost:8181}"
PROPERTIES_FILE="${PROPERTIES_FILE:-/properties.json}"
ITEMS_FILE="${ITEMS_FILE:-/items.json}"
MAPPING_FILE="${MAPPING_FILE:-/config/property-mapping.json}"
BACKEND_MAPPING_FILE="${BACKEND_MAPPING_FILE:-/app/storage/property-mapping.json}"
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

# Merge into an existing mapping so a growing catalogue adds new entities
# without recreating the ones already on the instance.
MAPPING="{}"
if [ -f "$MAPPING_FILE" ]; then
    EXISTING=$(jq -c '.' "$MAPPING_FILE" 2>/dev/null || echo "{}")
    if [ "$(echo "$EXISTING" | jq 'length')" -gt 0 ]; then
        MAPPING="$EXISTING"
        echo "[create-properties] Loaded $(echo "$MAPPING" | jq 'length') existing mappings."
    fi
fi

# ensure_entity <property|item> <wikidata_id> <label> <description> [datatype]
ensure_entity() {
    local kind="$1"
    local wikidata_id="$2"
    local label="$3"
    local description="$4"
    local datatype="$5"

    local mapped
    mapped=$(echo "$MAPPING" | jq -r --arg k "$wikidata_id" '.[$k] // empty')
    if [ -n "$mapped" ]; then
        echo "  ${wikidata_id} (${label}) already mapped to ${mapped}"
        return
    fi

    echo -n "  Creating ${wikidata_id} (${label})... "

    local encoded_label
    encoded_label=$(printf '%s' "$label" | jq -sRr @uri)
    local search_result
    search_result=$(curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
        "${MW_API}?action=wbsearchentities&search=${encoded_label}&language=en&type=${kind}&format=json")

    local local_id
    local_id=$(echo "$search_result" | jq -r --arg l "$label" \
        '(.search // [])[] | select(.label == $l) | .id' | head -n 1)

    if [ -n "$local_id" ]; then
        echo "already exists as ${local_id}"
    else
        local entity_data
        if [ "$kind" = "property" ]; then
            entity_data=$(jq -n --arg l "$label" --arg d "$description" --arg t "$datatype" \
                '{labels:{en:{language:"en",value:$l}},descriptions:{en:{language:"en",value:$d}},datatype:$t}')
        else
            entity_data=$(jq -n --arg l "$label" --arg d "$description" \
                '{labels:{en:{language:"en",value:$l}},descriptions:{en:{language:"en",value:$d}}}')
        fi

        local result
        result=$(curl -s -c /tmp/wb_cookies -b /tmp/wb_cookies \
            --data-urlencode "action=wbeditentity" \
            --data-urlencode "new=${kind}" \
            --data-urlencode "data=${entity_data}" \
            --data-urlencode "token=${CSRF_TOKEN}" \
            --data-urlencode "format=json" \
            "${MW_API}")

        local_id=$(echo "$result" | jq -r '.entity.id // empty')
        if [ -z "$local_id" ]; then
            echo "FAILED: $(echo "$result" | jq -r '.error.info // "unknown error"')"
            return
        fi
        echo "created as ${local_id}"
    fi

    MAPPING=$(echo "$MAPPING" | jq --arg k "$wikidata_id" --arg v "$local_id" '. + {($k): $v}')
}

echo "[create-properties] Ensuring properties from ${PROPERTIES_FILE}..."
PROP_COUNT=$(jq 'length' "$PROPERTIES_FILE")
for i in $(seq 0 $((PROP_COUNT - 1))); do
    ROW=$(jq -c ".[$i]" "$PROPERTIES_FILE")
    ensure_entity "property" \
        "$(echo "$ROW" | jq -r '.wikidata_id')" \
        "$(echo "$ROW" | jq -r '.label')" \
        "$(echo "$ROW" | jq -r '.description')" \
        "$(echo "$ROW" | jq -r '.datatype')"
done

echo "[create-properties] Ensuring items from ${ITEMS_FILE}..."
ITEM_COUNT=$(jq 'length' "$ITEMS_FILE")
for i in $(seq 0 $((ITEM_COUNT - 1))); do
    ROW=$(jq -c ".[$i]" "$ITEMS_FILE")
    ensure_entity "item" \
        "$(echo "$ROW" | jq -r '.wikidata_id')" \
        "$(echo "$ROW" | jq -r '.label')" \
        "$(echo "$ROW" | jq -r '.description')"
done

mkdir -p "$(dirname "$MAPPING_FILE")"
echo "$MAPPING" | jq '.' > "$MAPPING_FILE"
echo "[create-properties] Property mapping written to ${MAPPING_FILE}"

# The backend reads PROPERTY_MAPPING_PATH from its own storage volume. Write
# there too when the init container has it mounted.
if [ -d "$(dirname "$BACKEND_MAPPING_FILE")" ]; then
    echo "$MAPPING" | jq '.' > "$BACKEND_MAPPING_FILE"
    echo "[create-properties] Property mapping written to ${BACKEND_MAPPING_FILE}"
fi

echo "[create-properties] Done. $(echo "$MAPPING" | jq 'length') entity mappings available."
