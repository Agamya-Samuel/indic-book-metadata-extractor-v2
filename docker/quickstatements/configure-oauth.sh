#!/usr/bin/env bash
# Install the QuickStatements OAuth consumer credentials into the QS volume.
#
#   1. Create the Wikibase user QuickStatementsBot.
#   2. Register an owner-only consumer at
#      <wikibase>/wiki/Special:OAuthConsumerRegistration with callback
#      https://indic-book-metadata-extractor-quickstatements.nexio.uk/api.php
#      and the grant "Create, edit, and move pages".
#   3. Put the consumer key/secret in the environment:
#        QS_OAUTH_CONSUMER_KEY=...
#        QS_OAUTH_CONSUMER_SECRET=...
#   4. Run: ./docker/quickstatements/configure-oauth.sh <quickstatements-container>
set -euo pipefail

CONTAINER="${1:?usage: configure-oauth.sh <quickstatements-container>}"
: "${QS_OAUTH_CONSUMER_KEY:?QS_OAUTH_CONSUMER_KEY is not set}"
: "${QS_OAUTH_CONSUMER_SECRET:?QS_OAUTH_CONSUMER_SECRET is not set}"

cat > /tmp/qs-oauth.ini <<EOF
; HTTP User-Agent header
agent = OpenBookMap/1.0 (https://indic-book-metadata-extractor.nexio.uk)
; Consumer registered at Special:OAuthConsumerRegistration
consumerKey = ${QS_OAUTH_CONSUMER_KEY}
consumerSecret = ${QS_OAUTH_CONSUMER_SECRET}
EOF

docker cp /tmp/qs-oauth.ini "$CONTAINER:/quickstatements/data/oauth.ini"
echo "oauth.ini installed in $CONTAINER"