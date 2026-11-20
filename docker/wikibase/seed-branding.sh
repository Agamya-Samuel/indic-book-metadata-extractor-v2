#!/usr/bin/env bash
# Copy the OKI branding assets into a Wikibase container.
#
#   ./docker/wikibase/seed-branding.sh <wikibase-container>
#
# Current images bake the files into /var/www/html/branding (see Dockerfile),
# so this is only needed for an image built before that change, or a bare
# `docker run` of an upstream wikibase image. It is safe to re-run.
set -euo pipefail

CONTAINER="${1:?usage: seed-branding.sh <wikibase-container>}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker exec "$CONTAINER" mkdir -p /var/www/html/branding
for name in logo icon; do
    docker cp "$DIR/images/$name.png" "$CONTAINER:/var/www/html/branding/$name.png"
done

docker exec "$CONTAINER" apache2ctl graceful
echo "branding installed in $CONTAINER"