#!/usr/bin/env bash
# Copy the OKI branding assets into a Wikibase container's images volume.
#
#   ./docker/wikibase/seed-branding.sh <wikibase-container>
#
# The files live in the wikibase_data volume, so this only needs to run when
# the volume is created or recreated.
set -euo pipefail

CONTAINER="${1:?usage: seed-branding.sh <wikibase-container>}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker exec "$CONTAINER" mkdir -p /var/www/html/images/indico
for name in logo icon; do
    docker cp "$DIR/images/$name.png" "$CONTAINER:/var/www/html/images/indico/$name.png"
done

docker exec "$CONTAINER" apache2ctl graceful
echo "branding installed in $CONTAINER"