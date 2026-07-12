FROM wikibase/wikibase:7

# Install extensions not bundled in the wikibase:7 image.
# REL1_45 matches MediaWiki 1.45.x used by this image.
# --depth 1 keeps image size small.
RUN cd /var/www/html/extensions && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/PropertySuggester && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/WikibaseLexeme && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/WikibaseLexemeCirrusSearch && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/WikibaseQualityConstraints && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/AdvancedSearch

# Install curl for gadget fetching (may already be present)
RUN apt-get update && apt-get install -y --no-install-recommends curl jq && \
    rm -rf /var/lib/apt/lists/*

# Copy property creation script and definitions
COPY create-properties.sh /create-properties.sh
COPY properties.json /properties.json
RUN chmod +x /create-properties.sh

# Fetch gadget source files from wikidata.org at build time
COPY fetch-gadgets.sh /fetch-gadgets.sh
RUN chmod +x /fetch-gadgets.sh && /fetch-gadgets.sh || echo "WARN: gadget fetch failed, install-gadgets.sh will need manual run"

# Copy gadget installer
COPY install-gadgets.sh /install-gadgets.sh
RUN chmod +x /install-gadgets.sh
